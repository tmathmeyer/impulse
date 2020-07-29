
#ifndef IMPULSE_PROTO_PROTOLEX_H_
#define IMPULSE_PROTO_PROTOLEX_H_

#include <list>
#include <vector>

#include <impulse/lex/lex.h>

namespace impulse {
namespace proto {

enum class ProtoSyntax {
  kLineBreak,
  kWord,
  kNumber,
  kOpenBrace,
  kCloseBrace,
  kOpenBracket,
  kCloseBracket,
  kSemiColon,
  kComment,
  kPeriod,
  kType,
  kEnum,
  kUnion,
  kQuote,
  kCommentAnything,
};

template<typename Enum>
using TokenVector = std::vector<impulse::lex::Token<Enum>>;

template<typename Enum>
using TokenList = std::list<impulse::lex::Token<Enum>>;

using ProtoToken = impulse::lex::Token<ProtoSyntax>;

template<typename Enum>
TokenList<Enum> DropComments(TokenVector<Enum> vec) {
  TokenList<Enum> result;
  bool comment = false;
  for (const auto& T : vec) {
    if (T.type == Enum::kComment) {
      comment = true;
    }
    else if (T.type == Enum::kLineBreak) {
      comment = false;
    }
    else if (!comment) {
      result.push_back(T);
    }
  }
  return result;
}

TokenList<ProtoSyntax> LexFile(std::string filename);

}  // namespace proto
}  // namespace impulse

#endif  // ifndef IMPULSE_PROTO_PROTOLEX_H_