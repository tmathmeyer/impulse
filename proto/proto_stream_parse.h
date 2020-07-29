
#ifndef IMPULSE_PROTO_PROTO_STREAM_PARSE_H_
#define IMPULSE_PROTO_PROTO_STREAM_PARSE_H_

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protolex.h>
#include <impulse/base/status.h>

namespace impulse {
namespace proto {

template<typename T>
using ErrorOr = impulse::base::ErrorOr<T>;

/* Typedef the list ref to a shorter name */
using TokenStream = TokenList<ProtoSyntax>;

/* define the package as a vector of strings */
using Package = std::vector<std::string>;

/* Parse the proto stream! */
ErrorOr<ParseTree> parseProto(TokenStream& tokens);

}  // proto
}  // impulse

#endif  // IMPULSE_PROTO_PROTO_STREAM_PARSE_H_