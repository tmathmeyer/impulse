
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

namespace proto {

base::ErrorOr<Source> parseArgs(int argc, char **argv) {
  try {
    auto result = static_cast<Source*>(argparse::ParseArgs<Source>(argc, argv));
    return *result;
  } catch(...) {
    argparse::DisplayHelp<Source>();
    return base::Status(ProtoCodes::kFail);
  }
}

base::ErrorOr<base::Callback<base::Status(ParseTree)>> getFrontend(std::string lang) {
  if (lang == "python")
    return base::Bind(&frontend::generatePython);

  return base::Status(ProtoCodes::kUnsupportedLanguage).WithData("language",
    lang);
}

}  // namespace proto

using namespace argparse;

int main(int argc, char** argv) {
  auto args = base::checkCall(proto::parseArgs(argc, argv));
  auto check_tree = base::checkCall(proto::protoParse(args[0_arg_index]));

  auto language = args[1_arg_index];
  if (language) {
    auto frontend = base::checkCall(proto::getFrontend(language.value()));
    base::Status result = std::move(frontend).Run(std::move(check_tree));
    if (!result) std::move(result).dump();
  }

  return 0;
}