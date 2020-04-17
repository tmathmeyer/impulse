
#ifndef IMPULSE_PROTO_PROTOCOMPILE_H_
#define IMPULSE_PROTO_PROTOCOMPILE_H_

#include <tuple>
#include <vector>
#include <impulse/util/status.h>

namespace impulse {
namespace proto {

enum class ProtoCodes {
  kOk = 0,
  kFail = 1,

  kInvalidArguments = 2,
  kNoFile = 3,
  kInvalidCharacter = 4,
  kBadToken = 5,
  kRanOffEndOfTokens = 6,
  kUnsupportedLanguage = 7,
  kInvalidPath = 8,
};

struct MemberType {
  enum class Type { kBuiltin, kList, kUserDefined };
  Type type;
  std::string value;
  std::shared_ptr<MemberType> userDefined;
};

struct StructuralRepr {
  enum class Type { kType, kEnum, kUnion };
  Type type;
  std::string name;
  std::vector<std::string> package_parts;
  std::vector<std::string> enum_names;
  std::vector<std::tuple<std::string, MemberType>> member_names;
  std::vector<StructuralRepr> subtypes;
};

}  // namespace proto
}  // namespace impulse

#endif  // IMPULSE_PROTO_PROTOCOMPILE_H_
