
#ifndef IMPULSE_LEX_REGEX_H_
#define IMPULSE_LEX_REGEX_H_

#include <list>
#include <map>
#include <memory>
#include <vector>

#include <impulse/base/status.h>

namespace impulse {
namespace lex {

template<typename CharacterStorage>
class CharacterRange {
 public:
  CharacterRange(CharacterStorage low, CharacterStorage high)
    : CharacterRange(Type::kRange, low, high, std::nullopt) {}

  explicit CharacterRange(std::vector<CharacterStorage> options)
    : CharacterRange(Type::kSelection, std::nullopt, std::nullopt, options) {}

  explicit CharacterRange(bool all = true)
    : CharacterRange(all ? Type::kAll : Type::kNone,
                     std::nullopt,
                     std::nullopt,
                     std::nullopt) {}

  CharacterRange<CharacterStorage> And(CharacterRange<CharacterStorage>&& c) {
    if (type_ == Type::kNone)
      return c;

    if (c.type_ == Type::kNone)
      return *this;

    if (type_ == Type::kUnion) {
      inner_.value().push_back(c);
      return *this;
    }

    if (c.type_ == Type::kUnion) {
      c.inner_.value().push_back(*this);
      return c;
    }

    std::vector<CharacterRange<CharacterStorage>> val = {*this, c};
    return CharacterRange<CharacterStorage>(val);
  }

  bool contains(CharacterStorage c) const {
    switch(type_) {
      case Type::kRange:
        return c >= low_ && c <= high_;
      case Type::kAll:
        return true;
      case Type::kNone:
        return false;
      case Type::kSelection:
        for (const auto &e : options_.value())
          if (e == c)
            return true;
        return false;
      case Type::kUnion:
        for (const auto &e : inner_.value())
          if (e.contains(c))
            return true;
        return false;
    }
    return false;
  }

  void Print(bool newline = true) const {
    switch(type_) {
      case Type::kRange:
        printf("[%c - %c]", low_.value(), high_.value());
        break;
      case Type::kAll:
        printf("any");
        break;
      case Type::kNone:
        printf("none");
        break;
      case Type::kUnion:
        for (const auto &e : inner_.value())
          e.Print(false);
        break;
      case Type::kSelection:
        printf("{");
        for (const auto &e : options_.value())
          printf("%c,", e);
        printf("}");
        break;
    }
    if (newline)
      printf("\n");
  }

  bool operator<(const CharacterRange<CharacterStorage> c) const {
    if (c.type_ != type_)
      return type_ < c.type_;

    switch(type_) {
      case Type::kAll:
      case Type::kNone:
        return false;
      case Type::kRange:
        if (c.low_.value() != low_.value())
          return low_.value() < c.low_.value();
        if (c.high_.value() != high_.value())
          return high_.value() < c.high_.value();
        return false;
      case Type::kSelection:
        return options_.value() < c.options_.value();
      case Type::kUnion:
        return inner_.value() < c.inner_.value();
    }

    return false;
  }
 
 private:
  enum class Type { kRange = 0, kSelection = 1, kAll = 2, kNone = 3, kUnion = 4};

  CharacterRange(Type t, std::optional<CharacterStorage> low,
                         std::optional<CharacterStorage> high,
                         std::optional<std::vector<CharacterStorage>> opts)
    : type_(t), low_(low), high_(high), options_(opts), inner_(std::nullopt) {}

  CharacterRange(std::vector<CharacterRange<CharacterStorage>> wrapped)
    : type_(Type::kUnion),
      low_(std::nullopt),
      high_(std::nullopt),
      options_(std::nullopt),
      inner_(wrapped) {}

  Type type_;
  std::optional<CharacterStorage> low_;
  std::optional<CharacterStorage> high_;
  std::optional<std::vector<CharacterStorage>> options_;

  std::optional<std::vector<CharacterRange<CharacterStorage>>> inner_;

};

template<typename Enum>
class RegexGraph {
 public:
  using Range = CharacterRange<char>;
  using GraphPtr = std::shared_ptr<RegexGraph<Enum>>;
  using GraphState = std::tuple<std::string, GraphPtr>;

  std::map<Range, GraphPtr> graph;
  std::optional<Enum> finalState;

  RegexGraph() {}

  void AddMatchingValuesTo(char search, std::vector<GraphPtr>* v) const {
    for (const auto& r2g : graph) {
      if (r2g.first.contains(search)) {
        v->push_back(r2g.second);
      }
    }
  }

  void Print(int i = 0) {
    if (i == 0) {
      scroll_tok += 1;
      i = scroll_tok;
    } else if (i == scroll_tok) {
      return;
    }
    scroll_tok = i;

    printf("RegexGraphNode: %p\n", this);
    printf("  FinalState: %s\n", finalState.has_value() ? "yes" : "no");
    for (const auto& each : graph) {
      printf("  ");
      each.first.Print(false);
      printf(": %p\n", each.second.get());
    }
    puts("\n");
    for (const auto& each : graph) {
      each.second->Print(i);
    }
  }

  static GraphPtr Parse(std::string regex, Enum val) {
    if (regex.length() == 0)
      return nullptr;

    std::list<char> rex(regex.begin(), regex.end());
    return ParserHelper(rex, val);
  }

  static std::vector<GraphState> Search(
      std::string s, std::vector<GraphPtr> regecies) {
    if (s.length() == 0)
      return {};

    if (regecies.size() == 0)
      return {};

    std::list<char> str(s.begin(), s.end());
    std::vector<typename RegexGraph<Enum>::GraphState> states;
    for (const auto& state : regecies) {
      states.push_back(std::make_tuple(std::string(""), state));
    }

    while (str.size()) {
      for (const auto& state : states) {
        printf("\"%s\" ==> %p\n", std::get<0>(state).c_str(), std::get<1>(state).get());
      }
      printf("\n");

      char do_me = str.front();
      str.pop_front();

      std::vector<typename RegexGraph<Enum>::GraphState> new_states;
      for (const auto& state : states) {
        std::vector<RegexGraph<Enum>::GraphPtr> tmp;
        std::get<1>(state)->AddMatchingValuesTo(do_me, &tmp);
        std::string name = std::get<0>(state) + do_me;
        for (const auto& ns : tmp) {
          new_states.push_back(std::tie(name, ns));
        }
      }

      if (new_states.size() == 0) {
        return {};
      }

      states = new_states;
    }

    std::vector<typename RegexGraph<Enum>::GraphState> results;
    for (const auto& state : states) {
      if (std::get<1>(state)->finalState.has_value()) {
        results.push_back(state);
      }
    }
    return results;
  }

 private:
  int scroll_tok = 0;

  // helpers
  static GraphPtr ParserHelper(
      std::list<char> regex, std::optional<Enum> val) {

    if (regex.size() == 0)
      return nullptr;

    auto result = std::make_shared<RegexGraph<Enum>>();
    auto head = result;
    auto previous = head;
    auto prevRange = CharacterRange<char>();
    previous = nullptr;
    bool was_just_iterate = false;

    while (regex.size()) {
      char do_me = regex.front();
      
      if (do_me == '.') {
        was_just_iterate = false;
        previous = head;
        head = std::make_shared<RegexGraph<Enum>>();
        prevRange = CharacterRange<char>();
        previous->graph[prevRange] = head;
        regex.pop_front();
        continue;
      }

      if (do_me == '+') {
        if (was_just_iterate) {
          puts("Found duplicate regex iterations.");
          exit(1);
        }
        previous = head;
        previous->graph[prevRange] = head;
        was_just_iterate = true;
        regex.pop_front();
        continue;
      }

      if (do_me == '*') {
        if (was_just_iterate) {
          puts("Found duplicate regex iterations.");
          exit(1);
        }
        previous->graph[prevRange] = previous;
        head = previous;
        was_just_iterate = true;
        regex.pop_front();
        continue;
      }

      if (do_me == '[') {
        regex.pop_front();
        was_just_iterate = false;
        previous = head;
        head = std::make_shared<RegexGraph<Enum>>();
        prevRange = ParseRangeInner(regex);
        previous->graph[prevRange] = head;
        continue;
      }


      was_just_iterate = false;
      previous = head;
      head = std::make_shared<RegexGraph<Enum>>();
      std::vector<char> add = {do_me};
      prevRange = CharacterRange<char>(add);
      previous->graph[prevRange] = head;

      regex.pop_front();
    }

    head->finalState = val;

    return result;
  }

  static char getMetaChar(char f) {
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

  static CharacterRange<char> ParseRangeInner(std::list<char>& mod) {
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

};

}  // namespace lex
}  // namespace impulse

#endif  // IMPULSE_LEX_REGEX_H_
