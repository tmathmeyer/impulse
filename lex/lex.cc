
#include <impulse/lex/lex.h>

#include <iostream>
#include <fstream>
#include <regex>

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

template<typename Enum>
std::vector<Token<Enum>> Lexer<Enum>::Lex(std::istream& data) {
  std::vector<Token<Enum>> tokens;
  size_t lineNo = 0;

  for(;;) {
    lineNo++;
    std::optional<LexLine> line = readline(data);
    if (!line.has_value())
      return tokens;

    std::vector<std::tuple<size_t, std::string>> words = Split(line.value());
    for (const auto& word : words) {
      std::vector<Enum> matches;
      for (const auto& regex : compounds_) {
        if (std::regex_match(std::get<1>(word), regex.regex))
          matches.push_back(regex.type);
      }
    
      if (matches.size() != 1) {
        printf("Too many matches found for \"%s\"\n", std::get<1>(word).c_str());
        exit(1);
      }
      tokens.push_back({
        std::get<1>(word), lineNo, std::get<0>(word), line.value(),
        matches[0]
      });
    }
  }
}

template<typename Enum>
typename Lexer<Enum>::Regex Lexer<Enum>::Matcher(std::string regex, Enum type) {
  Lexer<Enum>::Regex result;
  try {
    result.regex = std::regex(regex);
  } catch (std::regex_error e) {
    printf("\"%s\" is not a valid regex\n", regex.c_str());
    exit(1);
  }
  result.type = type;
  return result;
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
    impulse::lex::Lexer<ProtoSyntax>::Matcher(
      "[a-zA-Z][a-zA-Z0-9]*", ProtoSyntax::kWord),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\{", ProtoSyntax::kOpenBrace),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\}", ProtoSyntax::kCloseBrace),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\[", ProtoSyntax::kOpenBracket),
    impulse::lex::Lexer<ProtoSyntax>::Matcher("\\]", ProtoSyntax::kCloseBracket),
    impulse::lex::Lexer<ProtoSyntax>::Matcher(";", ProtoSyntax::kSemiColon),
  });


  std::string path = "/home/ted/git/impulse/proto/example.proto";
  auto result = lexer->LexFile(path);
}