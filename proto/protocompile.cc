
// This parser is slow as shit - but I'm focusing on correctness rather than
// speed.

#include <stdio.h>
#include <tuple>
#include <vector>

#include <impulse/base/status.h>

#include <impulse/proto/commandline.h>
#include <impulse/proto/frontend/python.h>
#include <impulse/proto/protocompile.h>
#include <impulse/proto/protolex.h>
#include <impulse/proto/proto_stream_parse.h>

namespace impulse {
namespace proto {

using namespace argparse;

ErrorOr<Source> parseArgs(int argc, char **argv) {
  try {
    auto result = static_cast<Source*>(argparse::ParseArgs<Source>(argc, argv));
    return *result;
  } catch(...) {
    argparse::DisplayHelp<Source>();
    exit(1);
  }
}

ErrorOr<impulse::base::Callback<impulse::base::Status(ParseTree)>>
getFrontend(std::string lang) {
  if (lang == "python")
    return impulse::base::Bind(&frontend::generatePython);

  return impulse::base::Status(ProtoCodes::kUnsupportedLanguage).WithData(
    "language", lang);
}

int ProtoCompile(int argc, char** argv) {
  auto args = impulse::base::checkCall(parseArgs(argc, argv));
  auto language = args[1_arg_index];
  auto filename = args[0_arg_index];

  auto tokens = LexFile(filename);
  auto ast = impulse::base::checkCall(parseProto(tokens));

  if (language) {
    auto frontend = impulse::base::checkCall(getFrontend(language.value()));
    auto result = std::move(frontend).Run(std::move(ast));
    if (!result) {
      std::move(result).dump();
      return 1;
    }
  } else {
    puts("Syntax OK");
  }

  return 0;
}

}  // namespace proto
}  // namespace impulse


int main(int argc, char** argv) {
  return impulse::proto::ProtoCompile(argc, argv);
}