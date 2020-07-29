
#include <impulse/lex/lex.h>

#include <iostream>
#include <fstream>
#include <regex>

namespace impulse {
namespace lex {

std::vector<std::tuple<size_t, std::string>> Split(
    std::string s, CharacterRanges globable) {
  std::vector<std::tuple<size_t, std::string>> result;
  size_t position = 0;
  size_t last_position = 0;
  std::string tmp = "";
  bool isTokenString = true;
  for (const char &c : s) {
    position++;
    switch(c) {
      case ' ':
      case '\t':
      case '\n':
        if (tmp.length()) {
          result.push_back(std::make_tuple(last_position, tmp));
          tmp = "";
          isTokenString = true;
          last_position = position;
        }
        break;
      default:
        if (c == tmp.back() && !isTokenString) {
          tmp += c;
          break;
        }

        bool foundInGlob = false;
        for (const auto& range : globable) {
          if (c >= range.low && c <= range.high) {
            foundInGlob = true;
            break;
          }
        }

        if (foundInGlob && isTokenString) {
          tmp += c;
          break;
        }

        if (tmp.length()) {
          result.push_back(std::make_tuple(last_position, tmp));
          last_position = position;
          tmp = "";
        }
        
        tmp += c;
        isTokenString = foundInGlob;
    }
  }

  if (tmp.length()) {
    result.push_back(std::make_tuple(last_position, tmp));
  }

  return result;
}

}  // namespace lex
}  // namespace impulse