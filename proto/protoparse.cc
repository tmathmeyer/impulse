
#include <fstream>
#include <list>
#include <sstream>
#include <string>

#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {

util::Status generateErrorMessage(std::string preline,
                                  std::ifstream filestream,
                                  util::Status errorStatus,
                                  size_t line, size_t pos) {
  char c;
  while(filestream.get(c)) {
    if (c != '\n') {
      preline += c;
    } else {
      break;
    }
  }

  std::string pointer = "^- here";
  pointer.insert(pointer.begin(), pos - 2, ' ');

  errorStatus.WithData("line", std::to_string(line));
  errorStatus.WithData("column", std::to_string(pos));
  errorStatus.WithData("example", preline);
  errorStatus.WithData("hilight", pointer);
  return errorStatus;

}

util::ErrorOr<std::list<std::string>> stripCommentsTokenize(std::ifstream i) {
  enum class State { kNormal, kComment, kBlockComment };

  std::list<std::string> tokens;
  char c;
  std::string temporary;
  State state = State::kNormal;
  
  size_t line_number = 1;
  size_t char_position = 0;
  std::string error_current_line;

  while(i.get(c)) {
    if (c == '\n') {
      error_current_line = "";
      line_number++;
      char_position = 0;
    } else {
      error_current_line += c;
      char_position ++;
    }

    switch(state) {
      case State::kNormal:
        if (c == '/') {
          if (temporary == "/") {
            state = State::kComment;
            temporary = "";
            break;
          }
          if (temporary != "") {
            tokens.push_back(temporary);
          }
          temporary = c;
          break;
        }
        if (c == '*') {
          if (temporary == "/") {
            state = State::kBlockComment;
            temporary = "";
            break;
          }
          return generateErrorMessage(error_current_line, std::move(i),
            util::Status(ProtoCodes::kInvalidCharacter).WithData(
              "character", std::string(1, c)),
            line_number, char_position);
        }
        if (temporary == "/") {
          return generateErrorMessage(error_current_line, std::move(i),
            util::Status(ProtoCodes::kInvalidCharacter).WithData(
              "character", temporary),
            line_number, char_position);
        }
        if (c == ' ' || c == '\n' || c == '\t') {
          if (temporary != "") {
            tokens.push_back(temporary);
          }
          temporary = "";
          break;
        }
        if (c == ';' || c == '{' || c == '}' || c == '[' || c == ']') {
          if (temporary != "") {
            tokens.push_back(temporary);
          }
          tokens.push_back(std::string(1, c));
          temporary = "";
          break;
        }
        temporary += c;
      case State::kComment:
        if (c == '\n')
          state = State::kNormal;
        break;
      case State::kBlockComment:
        if (temporary == "" && c == '*') {
          temporary = "*";
          break;
        }
        if (temporary == "*" && c == '/')
          state = State::kNormal;
        temporary = "";
        break;
    }
  }

  if (temporary == "/") {
    return generateErrorMessage(error_current_line, std::move(i),
      util::Status(ProtoCodes::kInvalidCharacter).WithData("character", "/"),
      line_number, char_position);
  }

  return tokens;
}

#define CHECK_TOKEN_EXPLICIT(tokenlist, expected)                     \
do {                                                                  \
  std::string actual = pop(tokenlist);                                \
  if (actual != expected) {                                           \
    return util::Status(ProtoCodes::kBadToken).WithData(              \
      "message",                                                      \
      std::string("Expected \"") + expected                           \
                                 + "\" but found \""                  \
                                 + actual + "\"");                    \
  }                                                                   \
} while (0)

template<typename T>
T pop(std::list<T>& list) {
  if (!list.size())
    util::Status(ProtoCodes::kRanOffEndOfTokens).dump();
  T front = list.front();
  list.pop_front();
  return front;
}

std::vector<std::string> tokenToPackage(std::string pkg) {
  std::vector<std::string> package;
  std::stringstream splitter(pkg);
  std::string token;
  while(std::getline(splitter, token, '.'))
    package.push_back(token);
  return package;
}

util::Status checkNameIsNotBuiltin(std::string name) {
  if (name == "list" || name == "bool" || name == "string")
    return util::Status(ProtoCodes::kFail);
  if (name == "uint8" || name == "uint16" || name == "uint32" || name == "uint64")
    return util::Status(ProtoCodes::kFail);
  if (name == "int8" || name == "int16" || name == "int32" || name == "int64")
    return util::Status(ProtoCodes::kFail);
  return util::Status::Ok();
}

util::ErrorOr<StructuralRepr> tokensToEnumType(std::list<std::string>& tokens,
                                               std::vector<std::string> pkg) {
  StructuralRepr result = {};
  result.package_parts = pkg;
  result.type = StructuralRepr::Type::kEnum;
  result.name = pop(tokens);
  CHECK_TOKEN_EXPLICIT(tokens, "{");
  do {
    std::string next = pop(tokens);
    if (next == "}") {
      CHECK_TOKEN_EXPLICIT(tokens, ";");
      break;
    }

    auto check = checkNameIsNotBuiltin(next);
    if (!check)
      return check;

    result.enum_names.push_back(next);
    CHECK_TOKEN_EXPLICIT(tokens, ";");
  } while(true);
  return result;
}

util::ErrorOr<MemberType> tokensToMemberType(std::list<std::string>& tokens) {
  std::string next = pop(tokens);
  auto check = checkNameIsNotBuiltin(next);
  MemberType result;

  if (check) {
    // TODO better checks on this type existing.
    result.type = MemberType::Type::kUserDefined;
    result.value = next;
    return result;
  }

  if (next == "list") {
    CHECK_TOKEN_EXPLICIT(tokens, "[");
    auto check = tokensToMemberType(tokens);
    if (!check) return check;
    CHECK_TOKEN_EXPLICIT(tokens, "]");

    auto src = std::move(check).value();
    result.type = MemberType::Type::kList;
    result.userDefined.reset(new MemberType());
    result.userDefined->type = src.type;
    result.userDefined->value = src.value;
    result.userDefined->userDefined = std::move(src.userDefined);
    return result;
  }

  result.type = MemberType::Type::kBuiltin;
  result.value = next;
  return result;
}

util::ErrorOr<StructuralRepr> tokensToHelperType(std::list<std::string>& tokens,
                                                 StructuralRepr::Type type,
                                                 std::vector<std::string> pkg) {
  StructuralRepr result = {};
  result.type = type;
  result.name = pop(tokens);
  result.package_parts = pkg;
  CHECK_TOKEN_EXPLICIT(tokens, "{");

  do {
    std::string next = pop(tokens);
    if (next == "}") {
      CHECK_TOKEN_EXPLICIT(tokens, ";");
      break;
    }
    if (next == "type") {
      auto check = tokensToHelperType(tokens, StructuralRepr::Type::kType, pkg);
      if (!check) return std::move(check).error();
      result.subtypes.push_back(std::move(check).value());
      continue;
    }
    if (next == "enum") {
      auto check = tokensToEnumType(tokens, pkg);
      if (!check) return std::move(check).error();
      result.subtypes.push_back(std::move(check).value());
      continue;
    }
    if (next == "union") {
      auto check = tokensToHelperType(tokens, StructuralRepr::Type::kUnion, pkg);
      if (!check) return std::move(check).error();
      result.subtypes.push_back(std::move(check).value());
      continue;
    }

    auto check = checkNameIsNotBuiltin(next);
    if (!check)
      return check;

    auto check_type = tokensToMemberType(tokens);
    if (!check_type) return std::move(check_type).error();
    CHECK_TOKEN_EXPLICIT(tokens, ";");
    result.member_names.push_back(
      std::make_tuple(next, std::move(check_type).value()));
  } while(true);

  return result;
}

util::ErrorOr<StructuralRepr> tokensToTypeType(std::list<std::string>& tokens,
                                               std::vector<std::string> pkg) {
  return tokensToHelperType(tokens, StructuralRepr::Type::kType, pkg);
}

util::ErrorOr<StructuralRepr> tokensToUnionType(std::list<std::string>& tokens,
                                                std::vector<std::string> pkg) {
  return tokensToHelperType(tokens, StructuralRepr::Type::kUnion, pkg);
}

util::ErrorOr<StructuralRepr> tokensToType(std::list<std::string>& tokens,
                                           std::vector<std::string> package) {
  std::string token = pop(tokens);
  if (token == "type")
    return tokensToTypeType(tokens, package);
  if (token == "enum")
    return tokensToEnumType(tokens, package);
  if (token == "union")
    return tokensToUnionType(tokens, package);
  return util::Status(ProtoCodes::kBadToken).WithData(
    "message", "Expected (type|enum|union), but found " + token); 
}

util::ErrorOr<ParseTree> handleTokens(std::list<std::string> tokens) {
  ParseTree result;
  if (tokens.size() == 0)
    return result;

  CHECK_TOKEN_EXPLICIT(tokens, "package");
  std::vector<std::string> package = tokenToPackage(pop(tokens));
  CHECK_TOKEN_EXPLICIT(tokens, ";");
  
  while(tokens.size()) {
    auto check_some = tokensToType(tokens, package);
    if (!check_some) return std::move(check_some).error();
    result.push_back(std::move(check_some).value());
  }

  return result;
}

util::ErrorOr<ParseTree> protoParse(std::string filepath) {
  std::ifstream fileReader;
  fileReader.open(filepath);
  if (!fileReader)
    return util::Status(ProtoCodes::kNoFile).WithData("path", filepath);
  auto check_tokens = stripCommentsTokenize(std::move(fileReader));
  if (!check_tokens)
    return std::move(check_tokens).error();
  return handleTokens(std::move(check_tokens).value());
}

}  // namespace proto
}  // namespace impulse