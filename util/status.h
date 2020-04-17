
#ifndef CPPUTIL_STATUS_STATUS_H_
#define CPPUTIL_STATUS_STATUS_H_

#include <iostream>
#include <map>
#include <vector>

#include <impulse/util/bind.h>
#include <impulse/util/location.h>

namespace util {

enum class InternalCodes {
  kOk = 0,
  kFail = 1,
  kCantAddCause = 2,
};

class Status {
 private:
  // Status is just a wrapper for an internal unique ptr, in order to make
  // OK checks and moves really cheap.
  struct StatusInternal {
    std::vector<Status> causes;
    uint32_t code;
    std::vector<Location> stack;
    std::map<std::string, std::string> data;

    StatusInternal(uint32_t c, Location l) : code(c), stack({l}) {}
  };
  std::unique_ptr<StatusInternal> internal_;

  // private constructor for the static Ok method.
  Status() : internal_(nullptr) {}

 public:
  static Status Ok() { return Status(); }

  // Constructor that takes a code impl and reflects to get the typename
  // and enum value.
  template<typename CodeImpl>
  Status(CodeImpl code, Location location = Location::Current())
      : internal_(std::make_unique<StatusInternal>(
                       static_cast<uint32_t>(code), location)) {}

  // Move constructor that logs the move location.
  Status(Status&& o, Location log = Location::Current()) {
    *this = std::move(o);
    if (internal_) {
      // Keep std:: things out, in case it gets moved into an optional,
      // vector, etc.
      if (std::string(log.filename).find("/usr/include") == std::string::npos)
        internal_->stack.push_back(log);
    }
  }
  Status& operator=(Status&&) = default;

  // Adds a cause to an error status, or generates a new error from an OK status
  Status&& AddCause(Status&& cause) && {
    if (!internal_) {
      return Status(InternalCodes::kFail).AddCause(std::move(*this))
                                         .AddCause(std::move(cause));
    }
    internal_->causes.push_back(std::move(cause));
    return std::move(*this);
  }

  Status&& WithData(std::string key, std::string value) {
    if (!internal_)
      return Status(InternalCodes::kFail).AddCause(std::move(*this))
                                         .WithData(key, value);
    internal_->data[key] = value;
    return std::move(*this);
  }

  uint32_t code() const {
    if (!internal_)
      return 0;
    return internal_->code;
  }

  void dump() {
    std::cout << "Error code : 0x" << std::hex
              << code()
              << std::dec << std::endl;
    std::cout << " Data:" << std::endl;
    for (auto it = internal_->data.begin(); it != internal_->data.end(); it++)
      std::cout << "  " << it->first << " = " << it->second << std::endl;
    std::cout << " Stack trace:" << std::endl;
    for (auto it = internal_->stack.begin(); it != internal_->stack.end(); it++)
      std::cout << "  "
                << (*it).filename << ":" << (*it).line_number << std::endl;
    exit(code());
  };

  operator bool() const {
    return internal_ == nullptr;
  }
};

template<typename Acceptable>
class ErrorOr {
 private:
  std::optional<Status> error_;
  std::optional<Acceptable> accept;

  ErrorOr(std::optional<Status> b, std::optional<Acceptable> a)
    : error_(std::move(b)), accept(std::move(a)) {}

 public:
  ErrorOr(Status base) : ErrorOr(std::move(base), std::nullopt) {}
  ErrorOr(Acceptable a) : ErrorOr(std::nullopt, std::forward<Acceptable>(a)) {}

  operator bool const() {
    return !error_.has_value() && accept.has_value();
  }

  operator Acceptable() && {
    return std::move(accept.value());
  }

  operator Status() && {
    return std::move(error_.value());
  }

  Status error() && {
    return std::move(error_.value());
  }

  Acceptable value() && {
    return std::move(accept.value());
  }
};

template<typename T>
T checkCall(ErrorOr<T> status) {
  if (!status) {
    Status failure = std::move(status);
    failure.dump();
  }
  return status;
}

template<>
struct CallbackDefaultConstruct<Status> {
  static Status Construct() {
    return Status(InternalCodes::kFail);
  }
};

}  // namespace util

#endif  // CPPUTIL_STATUS_STATUS_H_
