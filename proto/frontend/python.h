
#ifndef IMPULSE_PROTO_FRONTEND_PYTHON_H_
#define IMPULSE_PROTO_FRONTEND_PYTHON_H_

#include <impulse/util/status.h>

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {
namespace frontend {

util::Status generatePython(ParseTree tree);

void writeClass(std::ofstream&, const StructuralRepr&, int);
void writeUnion(std::ofstream&, const StructuralRepr&, int);

}  // namespace frontend
}  // namespace proto
}  // namespace impulse

#endif  // IMPULSE_PROTO_FRONTEND_PYTHON_H_
