
#include <impulse/proto/frontend/python.h>

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {
namespace frontend {

util::Status generatePython(ParseTree tree) {
  return util::Status(ProtoCodes::kFail);
}

}  // namespace frontend
}  // namespace proto
}  // namespace impulse