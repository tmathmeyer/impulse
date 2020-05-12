
#ifndef IMPULSE_BASE_LOCATION_H_
#define IMPULSE_BASE_LOCATION_H_

namespace base {

class Location {
 public:
  char* filename;
  int line_number;

  static Location Current(const char* file = __builtin_FILE(),
                          int line = __builtin_LINE()) {
    return Location(file, line); 
  }

  Location() : Location("__none__", 0) {}

 private:
  Location(const char* file, int line)
    : filename((char *)file),
      line_number(line) {}
};

}  // namespace base

#endif  // IMPULSE_BASE_LOCATION_H_
