
#include <impulse/lex/regex.h>

#include <list>

namespace impulse {
namespace lex {

char getMetaChar(char f) {
  switch(f) {
    case '\\':
      return '\\';
    case '[':
      return '[';
    case ']':
      return ']';
    case '(':
      return '(';
    case ')':
      return ')';
    case '*':
      return '*';
    case '+':
      return '+';
    case '-':
      return '-';
    default:
      printf("\\%c is not a valid metacharacter in a regex\n", f);
      exit(1);
  }
  return '\b';
}

CharacterRange<char> ParseRangeInner(std::list<char>& mod) {
  std::vector<char> chars;

  while(true) {
    if (mod.size() == 0) {
      puts("never found a ]");
      exit(1);
    }

    char do_me = mod.front();

    if (do_me == '.') {
      puts(". not allowed in a [] block");
      exit(1);
    }

    if (do_me == '[') {
      puts("Can't start a new match block inside an existing block");
      exit(1);
    }

    if (do_me == ']') {
      mod.pop_front();
      if (chars.size() == 0) {
        return CharacterRange<char>(false);
      }
      return CharacterRange<char>(chars);
    }

    if (do_me == '\\') {
      mod.pop_front();
      if (!mod.size()) { continue; }
      chars.push_back(getMetaChar(mod.front()));
      mod.pop_front();
      continue;
    }

    if (do_me >= 'a' && do_me < 'z') {
      mod.pop_front();
      if (!mod.size()) { continue; }
      if (mod.front() == '-') {
        mod.pop_front();
        if (!mod.size()) { continue; }
        char top = mod.front();
        if (top > 'a' && top <= 'z' && top > do_me) {
          mod.pop_front();
          return CharacterRange(do_me, top).And(ParseRangeInner(mod));
        } else {
          printf(
            "Started matching range with %c but ended with %c\n", do_me, top);
          exit(1);
        }
      }
    }

    if (do_me >= 'A' && do_me < 'Z') {
      mod.pop_front();
      if (!mod.size()) { continue; }
      if (mod.front() == '-') {
        mod.pop_front();
        if (!mod.size()) { continue; }
        char top = mod.front();
        if (top > 'A' && top <= 'Z' && top > do_me) {
          mod.pop_front();
          return CharacterRange(do_me, top).And(ParseRangeInner(mod));
        } else {
          printf(
            "Started matching range with %c but ended with %c\n", do_me, top);
          exit(1);
        }
      }
    }

    if (do_me >= '0' && do_me < '9') {
      mod.pop_front();
      if (!mod.size()) { continue; }
      if (mod.front() == '-') {
        mod.pop_front();
        if (!mod.size()) { continue; }
        char top = mod.front();
        if (top > '0' && top <= '9' && top > do_me) {
          mod.pop_front();
          return CharacterRange(do_me, top).And(ParseRangeInner(mod));
        } else {
          printf(
            "Started matching range with %c but ended with %c\n", do_me, top);
          exit(1);
        }
      }
    }

    chars.push_back(do_me);
    mod.pop_front();
    continue;
  }
}


}  // namespace lex
}  // namespace impulse
