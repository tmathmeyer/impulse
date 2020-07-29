
// This parser is slow as shit - but I'm focusing on correctness rather than
// speed.

#include <stdio.h>
#include <tuple>
#include <vector>

#include <impulse/base/status.h>

#include <impulse/proto/commandline.h>
#include <impulse/proto/frontend/python.h>
#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {

impulse::base::ErrorOr<Source> parseArgs(int argc, char **argv) {
  try {
    auto result = static_cast<Source*>(argparse::ParseArgs<Source>(argc, argv));
    return *result;
  } catch(...) {
    argparse::DisplayHelp<Source>();
    return impulse::base::Status(ProtoCodes::kFail);
  }
}

impulse::base::ErrorOr<impulse::base::Callback<impulse::base::Status(ParseTree)>> getFrontend(std::string lang) {
  if (lang == "python")
    return impulse::base::Bind(&frontend::generatePython);

  return impulse::base::Status(ProtoCodes::kUnsupportedLanguage).WithData("language",
    lang);
}

}  // namespace proto
}  // namespace impulse

using namespace argparse;

int main(int argc, char** argv) {
  auto args = impulse::base::checkCall(impulse::proto::parseArgs(argc, argv));
  auto check_tree = impulse::base::checkCall(impulse::proto::protoParse(args[0_arg_index]));

  auto language = args[1_arg_index];
  if (language) {
    auto frontend = impulse::base::checkCall(impulse::proto::getFrontend(language.value()));
    impulse::base::Status result = std::move(frontend).Run(std::move(check_tree));
    if (!result) std::move(result).dump();
  }

  return 0;
}