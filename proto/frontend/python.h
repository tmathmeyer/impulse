
#ifndef IMPULSE_PROTO_FRONTEND_PYTHON_H_
#define IMPULSE_PROTO_FRONTEND_PYTHON_H_

#include <impulse/base/status.h>

#include <impulse/proto/protocompile.h>

namespace impulse {
namespace proto {
namespace frontend {

impulse::base::Status generatePython(proto::ParseTree tree);

void writeClass(std::ofstream&, const StructuralRepr&, int);
void writeUnion(std::ofstream&, const StructuralRepr&, int);

}  // namespace frontend
}  // namespace proto
}  // namespace impulse

#endif  // IMPULSE_PROTO_FRONTEND_PYTHON_H_
