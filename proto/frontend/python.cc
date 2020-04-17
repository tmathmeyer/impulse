
#include <impulse/proto/frontend/python.h>

#include <sys/stat.h>
#include <fstream>

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {
namespace frontend {

util::Status writeFile(std::ofstream out, const StructuralRepr& repr) {
  out << "from collections import namedtuple" << std::endl;

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
  }

  return util::Status::Ok();
}

}  // namespace frontend
}  // namespace proto
}  // namespace impulse