
#include "impulse/lex/lex.h"

#include <iostream>
#include <fstream>

namespace impulse {
namespace lex {

// static
template<typename Enum>
std::vector<Token<Enum>> Lexer<Enum>::LexFile(std::string path) {
  std::ifstream fileReader;
  fileReader.open(path);

  if(!fileReader) {
    puts("Bad filepath");
    exit(1);
  }

  return Lex(fileReader);
}

}  // namespace lex
}  // namespace impulse


enum class ProtoSyntax {
  kWord,
  kOpenBrace,
  kCloseBrace,
  kOpenBracket,
  kCloseBracket,
  kSemiColon
};

int main() {
  auto lexer = impulse::lex::Lexer<ProtoSyntax>::Create({
    impulse::lex::Lexer<ProtoSyntax>::Regex(
      "[a-zA-Z][a-zA-Z0-9]*", ProtoSyntax::kWord),
    impulse::lex::Lexer<ProtoSyntax>::Regex("{", ProtoSyntax::kOpenBrace),
    impulse::lex::Lexer<ProtoSyntax>::Regex("}", ProtoSyntax::kCloseBrace),
    impulse::lex::Lexer<ProtoSyntax>::Regex("\\[", ProtoSyntax::kOpenBracket),
    impulse::lex::Lexer<ProtoSyntax>::Regex("\\]", ProtoSyntax::kCloseBracket),
    impulse::lex::Lexer<ProtoSyntax>::Regex(";", ProtoSyntax::kSemiColon),
  });


  std::string path = "/home/ted/git/impulse/proto/example.proto";
  auto result = lexer->LexFile(path);
}