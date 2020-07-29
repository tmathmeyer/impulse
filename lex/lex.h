
#ifndef IMPULSE_LEX_LEX_H_
#define IMPULSE_LEX_LEX_H_

#include <fstream>
#include <iostream>
#include <memory>
#include <vector>

#include <regex>

namespace impulse {
namespace lex {

using LexLine = std::string;

struct CharacterRange {
  char low;
  char high;
};

using CharacterRanges = std::vector<CharacterRange>;

template<typename Enum>
struct Token {
  std::string value;
  size_t line;
  size_t position;
  LexLine source;
  Enum type;

  const void WriteTokenHighlight() {
    std::cout << std::string(source) << "\n"
              << std::string(position, ' ')
              << std::string(value.length(), '^')
              << "\n";
  }
};

std::vector<std::tuple<size_t, std::string>> Split(
    std::string s, CharacterRanges globable);

template<typename Enum>
class Lexer {
 public:
  struct Regex {
    std::basic_regex<char> regex;
    Enum type;
  };

  static Regex Matcher(std::string regex, Enum type) {
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

  static std::unique_ptr<Lexer<Enum>> Create(std::vector<Regex> compounds) {
    return std::make_unique<Lexer<Enum>>(std::move(compounds));
  }

  Lexer(std::vector<Regex> compounds) : compounds_(std::move(compounds)) {}

  std::vector<Token<Enum>> LexFile(std::string path, CharacterRanges globable) {
    std::ifstream fileReader;
    fileReader.open(path);

    if(!fileReader) {
      puts("Bad filepath");
      exit(1);
    }

    return Lex(fileReader, globable);
  }

  std::vector<Token<Enum>> Lex(std::istream& data, CharacterRanges globable) {
    std::vector<Token<Enum>> tokens;
    size_t lineNo = 0;

    for(;;) {
      lineNo++;
      std::optional<LexLine> line = readline(data);
      if (!line.has_value())
        return tokens;

      std::vector<std::tuple<size_t, std::string>> words = Split(
        line.value(), globable);
      for (const auto& word : words) {
        std::vector<Enum> matches;
        for (const auto& regex : compounds_) {
          if (std::regex_match(std::get<1>(word), regex.regex))
            matches.push_back(regex.type);
        }
      
        if (matches.size() == 0) {
          std::cout << "No matches found for \"" << std::get<1>(word) << "\""
                    << " on line " << lineNo << ":\n" << line.value() << "\n"
                    << std::string(std::get<0>(word), ' ')
                    << std::string(std::get<1>(word).length(), '^')
                    << "\n";
          exit(1);
        }
        tokens.push_back({
          std::get<1>(word), lineNo, std::get<0>(word), line.value(),
          matches[0]
        });
      }
      tokens.push_back({"", lineNo+1, 0, "", Enum::kLineBreak});
    }
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

  std::vector<Regex> compounds_;
};

}  // namespace lex
}  // namespace impulse

#endif  // IMPULSE_LEX_LEX_H_
