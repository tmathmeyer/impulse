
// This parser is slow as shit - but I'm focusing on correctness rather than
// speed.

#include <stdio.h>
#include <tuple>
#include <vector>

#include <impulse/util/status.h>

#include <impulse/proto/protocompile.h>
#include <impulse/proto/protoparse.h>
#include <impulse/proto/frontend/python.h>

void help() {
  puts("protocompile <language> <file> [optional --verbose]");
  exit(1);
}

namespace impulse {
namespace proto {

using ArgResult = std::tuple<std::string, std::string>;
util::ErrorOr<ArgResult> getArguments(int argc, char** argv) {
  if (argc != 3 && argc != 4)
    return util::Status(ProtoCodes::kInvalidArguments);

  std::string verbose_flag = "--verbose";
  if (argc == 3) {
    if (argv[1] == verbose_flag || argv[2] == verbose_flag)
      return util::Status(ProtoCodes::kInvalidArguments);
    return std::make_tuple(std::string(argv[1]), std::string(argv[2]));
  }

  std::string arg1 = "";
  std::string arg2 = "";
  if (argv[1] == verbose_flag) {
    arg1 = argv[2];
    arg2 = argv[3];
  } else if (argv[2] == verbose_flag) {
    arg1 = argv[1];
    arg2 = argv[3];
  } else if (argv[3] == verbose_flag) {
    arg1 = argv[1];
    arg2 = argv[2];
  } else {
    return util::Status(ProtoCodes::kInvalidArguments);
  }

  return std::make_tuple(arg1, arg2);
}

util::ErrorOr<util::Callback<util::Status(ParseTree)>> getFrontend(std::string lang) {
  if (lang == "python")
    return util::Bind(&frontend::generatePython);

  return util::Status(ProtoCodes::kUnsupportedLanguage).WithData("language",
    lang);
}

}  // namespace proto
}  // namespace impulse


int main(int argc, char** argv) {
  if (argc != 3 && argc != 4) {
    help();
    exit(1);
  }

  // TODO switch to the cppargs arg parser.
  auto args = util::checkCall(impulse::proto::getArguments(argc, argv));
  auto frontend = util::checkCall(impulse::proto::getFrontend(std::get<0>(args)));
  auto check_tree = util::checkCall(impulse::proto::protoParse(std::get<1>(args)));

  std::move(frontend).Run(std::move(check_tree)).dump();
}