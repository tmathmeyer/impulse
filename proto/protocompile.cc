
// This parser is slow as shit - but I'm focusing on correctness rather than
// speed.

#include <stdio.h>
#include <tuple>
#include <vector>

#include <impulse/util/status.h>

#include <impulse/proto/commandline.h>
#include <impulse/proto/frontend/python.h>
#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>

namespace impulse {
namespace proto {

util::ErrorOr<Source> parseArgs(int argc, char **argv) {
  try {
    auto result = static_cast<Source*>(argparse::ParseArgs<Source>(argc, argv));
    return *result;
  } catch(...) {
    argparse::DisplayHelp<Source>();
    return util::Status(ProtoCodes::kFail);
  }
}

util::ErrorOr<util::Callback<util::Status(ParseTree)>> getFrontend(std::string lang) {
  if (lang == "python")
    return util::Bind(&frontend::generatePython);

  return util::Status(ProtoCodes::kUnsupportedLanguage).WithData("language",
    lang);
}

}  // namespace proto
}  // namespace impulse

using namespace argparse;

int main(int argc, char** argv) {
  auto args = util::checkCall(impulse::proto::parseArgs(argc, argv));
  auto check_tree = util::checkCall(impulse::proto::protoParse(args[0_arg_index]));

  auto language = args[1_arg_index];
  if (language) {
    auto frontend = util::checkCall(impulse::proto::getFrontend(language.value()));
    util::Status result = std::move(frontend).Run(std::move(check_tree));
    if (!result) std::move(result).dump();
  }

  return 0;
}