

#include <impulse/proto/proto_stream_parse.h>


/* Macro for ending loops where the data should have been processed */
#define LOOP_EXITED() \
impulse::base::Status(ProtoCodes::kRanOffEndOfTokens)


/* Macro for generating token assertion checker functions */
#define ASSERT_HELPER(Cap, Ref)                               \
template<typename AutoType>                                   \
inline ProtoToken AssertNextToken##Cap(TokenStream& tokens,    \
                                       AutoType expected,     \
                                       std::string message) { \
  ProtoToken token = pop(tokens);                             \
  if (expected != token.Ref)                                  \
    ErrorToken(token, message);                               \
  return token;                                               \
}


namespace impulse {
namespace proto {

/* A list-popping function */
template<typename T>
T pop(std::list<T>& list) {
  if (!list.size())
    base::Status(ProtoCodes::kRanOffEndOfTokens).dump();
  T front = list.front();
  list.pop_front();
  return front;
}


/* Dumps a token to console with a message */
void ErrorToken(ProtoToken token, std::string expected) {
  std::cout << "line " << token.line
            << ": Expected \"" << expected << "\", but found \""
            << token.value << "\"\n";
  token.WriteTokenHighlight();
  exit(1);
}


/* Add checkers for all the token fields */
// AssertNextTokenValue
ASSERT_HELPER(Value, value)
// AssertNextTokenType
ASSERT_HELPER(Type, type)


/* parse the package line */
ErrorOr<Package> getPackage(TokenStream& tokens) {
  // Drop the package string, its just there for decoration.
  AssertNextTokenValue(tokens, "package", "package");
  
  Package result;
  ProtoToken word = AssertNextTokenType(
    tokens, ProtoSyntax::kWord, "[string]");
  result.push_back(word.value);

  for(;;) {
    ProtoToken next = pop(tokens);
    switch(next.type) {
      case ProtoSyntax::kPeriod:
        break;
      case ProtoSyntax::kSemiColon:
        return result;
      default:
        ErrorToken(next, ". or ;");
    }

    ProtoToken word = AssertNextTokenType(
      tokens, ProtoSyntax::kWord, "[string]");
    result.push_back(word.value);
  }

  return LOOP_EXITED();
}


/* parse an enum definition */
ErrorOr<StructuralRepr> getEnum(TokenStream& tokens, Package package) {
  ProtoToken name = AssertNextTokenType(
    tokens, ProtoSyntax::kWord, "enum name");
  AssertNextTokenType(tokens, ProtoSyntax::kOpenBrace, "{");

  std::vector<std::string> enum_names;
  bool done = false;
  while(!done) {
    ProtoToken next = pop(tokens);
    switch(next.type) {
      case ProtoSyntax::kWord:
        enum_names.push_back(next.value);
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");
        break;
      case ProtoSyntax::kCloseBrace:
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");
        done = true;
        break;
      default:
        ErrorToken(next, "enum entry or }");
    }
  }

  StructuralRepr result = {
    StructuralRepr::Type::kEnum,
    name.value, package, enum_names, {}, {}};
  return result;
}


/* Check whether a type is a builtin type */
bool isBuiltin(std::string name) {
  if (name == "list" || name == "bool" || name == "string")
    return true;
  if (name == "uint8" || name == "uint16" || name == "uint32" || name == "uint64")
    return true;
  if (name == "int8" || name == "int16" || name == "int32" || name == "int64")
    return true;
  return false;
}


/* Parse a field type */
ErrorOr<MemberType> getFieldType(TokenStream& tokens) {
  ProtoToken next = pop(tokens);
  MemberType result;
  switch(next.type) {
    // Check for a normal type
    case ProtoSyntax::kWord:
      if (isBuiltin(next.value))
        result = {MemberType::Type::kBuiltin, next.value, nullptr, nullptr};
      result = {MemberType::Type::kUserDefined, next.value, nullptr, nullptr};
      return result;

    // check for an array type
    case ProtoSyntax::kOpenBracket: {
      auto check_field = getFieldType(tokens);
      if (!check_field) return std::move(check_field).error();
      AssertNextTokenType(tokens, ProtoSyntax::kCloseBracket, "]");
      auto list = std::make_shared<MemberType>();
      auto nested = std::move(check_field).value();
      list->type = nested.type;
      list->value = nested.value;
      list->listValue = nested.listValue;
      result = {MemberType::Type::kList, "", list, nullptr};
      return result;
    }

    // Fail on anything else
    default:
      ErrorToken(next, "typename or array");
  }

  return LOOP_EXITED();
}


/* Parse a union definition */
ErrorOr<StructuralRepr> getUnion(TokenStream& tokens, Package package) {
  ProtoToken name = AssertNextTokenType(
    tokens, ProtoSyntax::kWord, "union name");
  AssertNextTokenType(tokens, ProtoSyntax::kOpenBrace, "{");

  std::vector<std::tuple<std::string, MemberType>> members;
  bool done = false;
  while(!done) {
    ProtoToken next = pop(tokens);
    switch(next.type) {
      case ProtoSyntax::kWord: {
        // This token was a field name, so a type and ; follow.
        auto check_field = getFieldType(tokens);
        if (!check_field) return std::move(check_field).error();

        // Assert semicolon
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");

        // Push the type.
        members.push_back(std::make_tuple(
          next.value, std::move(check_field).value()));
        break;
      }

      case ProtoSyntax::kCloseBrace:
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");
        done = true;
        break;
      default:
        ErrorToken(next, "union entry or }");
    }
  }

  StructuralRepr result = {
    StructuralRepr::Type::kUnion,
    name.value, package, {}, members, {}};
  return result;
}


ErrorOr<StructuralRepr> getType(TokenStream& tokens, Package package) {
  ProtoToken name = AssertNextTokenType(
    tokens, ProtoSyntax::kWord, "type name");
  AssertNextTokenType(tokens, ProtoSyntax::kOpenBrace, "{");

  bool done = false;

  // members
  std::vector<std::tuple<std::string, MemberType>> members;

  // subtypes
  std::vector<StructuralRepr> subtypes;

  while(!done) {
    ProtoToken next = pop(tokens);
    switch(next.type) {
      // A field entry
      case ProtoSyntax::kWord: {
        // This token was a field name, so a type and ; follow.
        auto check_field = getFieldType(tokens);
        if (!check_field) return std::move(check_field).error();

        // Assert semicolon
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");

        // Push the type.
        members.push_back(std::make_tuple(
          next.value, std::move(check_field).value()));
        break;
      }

      // A nested type
      case ProtoSyntax::kType: {
        auto check_type = getType(tokens, package);
        if (!check_type) return std::move(check_type).error();
        subtypes.push_back(std::move(check_type).value());
        break;
      }

      // A nested enum
      case ProtoSyntax::kEnum: {
        auto check_enum = getEnum(tokens, package);
        if (!check_enum) return std::move(check_enum).error();
        subtypes.push_back(std::move(check_enum).value());
        break;
      }

      // A nested union
      case ProtoSyntax::kUnion: {
        auto check_union = getUnion(tokens, package);
        if (!check_union) return std::move(check_union).error();
        subtypes.push_back(std::move(check_union).value());
        break;
      }

      case ProtoSyntax::kCloseBrace:
        AssertNextTokenType(tokens, ProtoSyntax::kSemiColon, ";");
        done = true;
        break;

      default:
        ErrorToken(next, "field, or nested type");
    }
  }

  StructuralRepr result = {
    StructuralRepr::Type::kType,
    name.value, package, {}, members, subtypes};
  return result;
}


ErrorOr<ParseTree> getTypes(TokenStream& tokens, Package package) {
  ParseTree result;

  while(tokens.size()) {
    AssertNextTokenType(tokens, ProtoSyntax::kType, "type");

    auto check_type = getType(tokens, package);
    if (!check_type) return std::move(check_type).error();

    result.push_back(std::move(check_type).value());
  }

  return result;
}


ErrorOr<ParseTree> parseProto(TokenStream& tokens) {
  auto check_package = getPackage(tokens);
  if (!check_package) return std::move(check_package).error();

  return getTypes(tokens, std::move(check_package).value());
}

}  // proto
}  // impulse