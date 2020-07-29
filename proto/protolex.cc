
#include <impulse/proto/protolex.h>
#include <impulse/lex/lex.h>

namespace impulse {
namespace proto {

TokenList<ProtoSyntax> LexFile(std::string filename) {
  auto lexer = impulse::lex::Lexer<ProtoSyntax>::Create({
    impulse::lex::Lexer<ProtoSyntax>::Matcher("type", ProtoSyntax::kType),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("enum", ProtoSyntax::kEnum),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("union", ProtoSyntax::kUnion),
    impulse::lex::Lexer<ProtoSyntax>::Matcher(
      "[a-zA-Z_][a-zA-Z0-9_]*", ProtoSyntax::kWord),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\{", ProtoSyntax::kOpenBrace),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\}", ProtoSyntax::kCloseBrace),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\[", ProtoSyntax::kOpenBracket),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\]", ProtoSyntax::kCloseBracket),
    impulse::lex::Lexer<ProtoSyntax>::Matcher(";", ProtoSyntax::kSemiColon),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("//.*", ProtoSyntax::kComment),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\.", ProtoSyntax::kPeriod),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\"", ProtoSyntax::kQuote),
    impulse::lex::Lexer<ProtoSyntax>::Matcher(".*", ProtoSyntax::kCommentAnything),
  });

  impulse::lex::CharacterRanges token_symbols = {
    {'a', 'z'}, {'A', 'Z'},
    {'0', '9'}, {'_', '_'}
  };

  return DropComments(lexer->LexFile(filename, token_symbols));
}


}  // namespace proto
}  // namespace impulse