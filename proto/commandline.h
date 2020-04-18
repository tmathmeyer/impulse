
#include <string>
#include <optional>
#include <cppargs/argparse.h>

Flag(Source, "--proto", "-p",
"The Proto definition file, an an optional language."
" If no language is given, syntax will be verified."
" Supported languages: {Python}");
Arg(Source, std::string, std::optional<std::string>);
