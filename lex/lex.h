
#ifndef IMPULSE_LEX_LEX_H_
#define IMPULSE_LEX_LEX_H_

#include <iostream>
#include <memory>
#include <vector>

#include <impulse/lex/regex.h>

namespace impulse {
namespace lex {

using LexLine = std::string;

template<typename Enum>
struct Token {
  std::string value;
  size_t line;
  size_t position;
  LexLine source;
  Enum type;
};

std::vector<std::tuple<size_t, std::string>> Split(std::string s) {
  std::vector<std::tuple<size_t, std::string>> result;
  size_t position = 0;
  std::string tmp = "";
  for (const char &c : s) {
    position++;
    switch(c) {
      case ' ':
      case '\t':
      case '\n':
        if (tmp.length()) result.push_back(std::make_tuple(position, tmp));
        break;
      default:
        tmp += c;
    }
  }
  return result;
}


template<typename Enum>
class Lexer {
 public:
  using Compound = typename RegexGraph<Enum>::GraphPtr;

  static std::unique_ptr<Lexer<Enum>> Create(std::vector<Compound> compounds) {
    return std::make_unique<Lexer<Enum>>(std::move(compounds));
  }

  Lexer(std::vector<Compound> compounds) : compounds_(std::move(compounds)) {}


  std::vector<Token<Enum>> LexFile(std::string path);

  std::vector<Token<Enum>> Lex(std::istream& data) {
    std::vector<Token<Enum>> tokens;
    size_t lineNo = 0;

    for(;;) {
      lineNo++;
      std::optional<LexLine> line = readline(data);
      if (!line.has_value())
        return tokens;

      std::vector<std::tuple<size_t, std::string>> words = Split(line.value());
      for (const auto& word : words) {
        auto matches = RegexGraph<Enum>::Search(std::get<1>(word), compounds_);
        if (matches.size() == 0) {
          printf("No matches found for \"%s\"\n", std::get<1>(word).c_str());
          exit(1);
        }
        if (matches.size() != 1) {
          printf("Too many matches found for \"%s\"\n", std::get<1>(word).c_str());
          exit(1);
        }
        tokens.push_back({
          std::get<1>(word), lineNo, std::get<0>(word), line.value(),
          std::get<1>(matches[0])->finalState.value()
        });
      }
    }
  }

  static Compound Regex(std::string value, Enum key) {
    return RegexGraph<Enum>::Parse(value, key);
  }

 private:
  std::optional<LexLine> readline(std::istream& stream) {
    std::string result = "";
    char buf[256];
    do {
      stream.getline(buf, 256);
      result += std::string(buf);
    } while(stream.gcount() == 255);

    if (stream.gcount() == 0)
      return std::nullopt;
    return result;
  }

  std::vector<Compound> compounds_;
};


}  // namespace lex
}  // namespace impulse

#endif  // IMPULSE_LEX_LEX_H_
