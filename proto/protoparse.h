
#ifndef IMPULSE_PROTO_PROTOPARSE_H_
#define IMPULSE_PROTO_PROTOPARSE_H_

#include <tuple>
#include <vector>

#include <impulse/base/status.h>

#include <impulse/proto/protocompile.h>

namespace impulse {
namespace proto {

using ParseTree = std::vector<StructuralRepr>;
impulse::base::ErrorOr<ParseTree> protoParse(std::string filepath);

}  // namespace proto
}  // namespace impulse

#endif  // IMPULSE_PROTO_PROTOPARSE_H_