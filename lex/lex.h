
#ifndef IMPULSE_LEX_LEX_H_
#define IMPULSE_LEX_LEX_H_

#include <iostream>
#include <memory>
#include <vector>

#include <regex>

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
  struct Regex {
    std::basic_regex<char> regex;
    Enum type;
  };

  static Regex Matcher(std::string regex, Enum type);
  static std::unique_ptr<Lexer<Enum>> Create(std::vector<Regex> compounds) {
    return std::make_unique<Lexer<Enum>>(std::move(compounds));
  }

  Lexer(std::vector<Regex> compounds) : compounds_(std::move(compounds)) {}

  std::vector<Token<Enum>> LexFile(std::string path);
  std::vector<Token<Enum>> Lex(std::istream& data);

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

  std::vector<Regex> compounds_;
};


}  // namespace lex
}  // namespace impulse

#endif  // IMPULSE_LEX_LEX_H_
