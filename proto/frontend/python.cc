
#include <impulse/proto/frontend/python.h>

#include <fstream>
#include <map>
#include <sys/stat.h>
#include <vector>

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {
namespace frontend {

std::string idt(int indent) {
  if (indent == 0)
    return "";
  std::string result = "  ";
  while (indent > 1) {
    if (indent % 2 == 0) {
      result += result;
      indent /= 2;
    } else {
      result = result + result + "  ";
      indent = (indent - 1) / 2;
    }
  }
  return result;
}

void writeEnum(std::ofstream& out, const StructuralRepr& repr, int indent) {
  out << idt(indent) << "class " << repr.name << "(Enum):" << std::endl;
  auto nidt = idt(indent + 1);

  for (std::string entry : repr.enum_names) {
    out << nidt << entry << " = auto()" << std::endl;
  }
}

void writeSubtype(std::ofstream& out, const StructuralRepr& repr, int indent) {
  if (repr.type == StructuralRepr::Type::kEnum)
    writeEnum(out, repr, indent);
  else if (repr.type == StructuralRepr::Type::kType)
    writeClass(out, repr, indent);
  else if (repr.type == StructuralRepr::Type::kUnion)
    writeUnion(out, repr, indent);
}

void writeClass(std::ofstream& out, const StructuralRepr& repr, int indent) {
  out << idt(indent) << "class " << repr.name << "(object):" << std::endl;
  std::map<std::string, MemberType> mapping;
  std::string commalist = "";
  std::string commalist_strs = "";
  std::vector<std::string> typenames;

  for (const auto& tup : repr.member_names) {
    mapping[std::get<0>(tup)] = std::get<1>(tup);
    if (commalist != "") {
      commalist += ", ";
      commalist_strs += ", ";
    }
    commalist += std::get<0>(tup);
    commalist_strs += "'" + std::get<0>(tup) + "'";
    typenames.push_back(std::get<0>(tup));
  }

  auto cls_idt = idt(indent + 1);
  auto method_idt = idt(indent + 2);

  out << cls_idt << "__slots__ = (" << commalist_strs << ")" << std::endl;
  out << std::endl;

  for (const auto& sub : repr.subtypes) {
    writeSubtype(out, sub, indent+1);
    out << std::endl;
  }

  // TODO check types in constructor!
  out << cls_idt << "def __init__(self, " << commalist << "):" << std::endl;
  for (std::string typname : typenames) {
    out << method_idt << "self." << typname << " = " << typname << std::endl;
  }
}

void writeUnion(std::ofstream& out, const StructuralRepr& repr, int indent) {
  out << idt(indent) << "class " << repr.name << "(object):" << std::endl;
  std::map<std::string, MemberType> mapping;
  std::string commalist_strs = "'_actual'";
  std::vector<std::string> typenames;

  for (const auto& tup : repr.member_names) {
    mapping[std::get<0>(tup)] = std::get<1>(tup);
    if (commalist_strs != "")
      commalist_strs += ", ";
    commalist_strs += "'" + std::get<0>(tup) + "'";
    typenames.push_back(std::get<0>(tup));
  }

  auto cls_idt = idt(indent + 1);
  auto method_idt = idt(indent + 2);

  out << cls_idt << "__slots__ = (" << commalist_strs << ")" << std::endl;
  out << std::endl;

  for (const auto& sub : repr.subtypes) {
    writeSubtype(out, sub, indent+1);
    out << std::endl;
  }

  // TODO check types in constructor!
  out << cls_idt << "def __init__(self, **kwargs):" << std::endl;
  out << method_idt << "assert len(kwargs) == 1" << std::endl;
  out << method_idt << "self._actual = list(kwargs.keys())[0]" << std::endl;
  out << method_idt << "setattr(self, self._actual, kwargs[self._actual])";
  out << std::endl << std::endl;
  out << cls_idt << "def __getattribute__(self, attr):" << std::endl;
  out << method_idt << "if attr == '_actual':" << std::endl;
  out << method_idt << "  return object.__getattribute__(self, attr)" << std::endl;
  out << method_idt << "if attr == 'getUnionKey':" << std::endl;
  out << method_idt << "  return object.__getattribute__(self, attr)" << std::endl;
  out << method_idt << "assert attr == self._actual" << std::endl;
  out << method_idt << "return object.__getattribute__(self, attr)" << std::endl;
  out << std::endl;
  out << cls_idt << "def getUnionKey(self):" << std::endl;
  out << method_idt << "return self._actual" << std::endl;
}

util::Status writeFile(std::ofstream out, const StructuralRepr& repr) {
  out << "from collections import namedtuple" << std::endl;
  out << "from enum import Enum, auto" << std::endl;
  out << std::endl;

  if (repr.type == StructuralRepr::Type::kEnum)
    writeEnum(out, repr, 0);
  else if (repr.type == StructuralRepr::Type::kType)
    writeClass(out, repr, 0);
  else if (repr.type == StructuralRepr::Type::kUnion)
    writeUnion(out, repr, 0);

  return util::Status::Ok();
}

util::ErrorOr<std::string> getFilePath(const StructuralRepr& repr) {
  std::string dirSoFar = "";
  for (std::string part : repr.package_parts) {
    dirSoFar += part + "/";
    if (mkdir(dirSoFar.c_str(), 0755) != 0 && errno != EEXIST)
      return util::Status(ProtoCodes::kInvalidPath).WithData(
        "errno", std::to_string(errno));
  }

  return dirSoFar + repr.name + ".py";
}

util::Status generatePython(ParseTree tree) {
  for (const auto& type : tree) {
    auto check_filepath = getFilePath(type);
    if (!check_filepath)
      return std::move(check_filepath).error();

    const auto path = std::move(check_filepath).value();
    std::ofstream pyfile(path);
    if (!pyfile.is_open())
      return util::Status(ProtoCodes::kInvalidPath).WithData("path", path);

    auto writeOK = writeFile(std::move(pyfile), type);
    if (!writeOK) return writeOK;
    puts(path.c_str());
  }

  return util::Status::Ok();
}

}  // namespace frontend
}  // namespace proto
}  // namespace impulse