
#ifndef CPPUTIL_BIND_BIND_H_
#define CPPUTIL_BIND_BIND_H_

#include <stddef.h>
#include <utility>
#include <memory>
#include <tuple>

#include <impulse/util/location.h>

namespace util {

template<typename... Types>
struct TypeList {};

template<size_t n, typename List>
struct DropTypeListImpl;

template<size_t n, typename T, typename... List>
struct DropTypeListImpl<n, TypeList<T, List...>>
       : DropTypeListImpl<n - 1, TypeList<List...>> {};

template<typename T, typename... List>
struct DropTypeListImpl<0, TypeList<T, List...>> {
  using Type = TypeList<T, List...>;
};

template<>
struct DropTypeListImpl<0, TypeList<>> {
  using Type = TypeList<>;
};

template<size_t n, typename List, typename... Pile>
struct TakeTypeListImpl;

template<size_t n, typename T, typename... List, typename... Pile>
struct TakeTypeListImpl<n, TypeList<T, List...>, Pile...>
       : TakeTypeListImpl<n - 1, TypeList<List...>, Pile..., T> {};

template<typename T, typename... List, typename... Pile>
struct TakeTypeListImpl<0, TypeList<T, List...>, Pile...> {
  using Type = TypeList<Pile...>;
  using TupleType = std::tuple<Pile...>;
};

template<typename... Pile>
struct TakeTypeListImpl<0, TypeList<>, Pile...> {
  using Type = TypeList<Pile...>;
  using TupleType = std::tuple<Pile...>;
};

template<typename R, typename List>
struct MakeFunctionTypeImpl;

template<typename R, typename... Args>
struct MakeFunctionTypeImpl<R, TypeList<Args...>> {
  typedef R Type(Args...);
};

template<typename R, typename ArgList>
using MakeFunctionType = typename MakeFunctionTypeImpl<R, ArgList>::Type;

template<typename Signature>
struct ExtractArgsImpl;

template<typename Return, typename... Args>
struct ExtractArgsImpl<Return(Args...)> {
  using ReturnType = Return;
  using ArgsList = TypeList<Args...>;
};

template<typename Signature>
using ExtractArgs = typename ExtractArgsImpl<Signature>::ArgsList;

template<typename Signature>
using ExtractReturn = typename ExtractArgsImpl<Signature>::ReturnType;

template<typename Functor>
struct MakeFunctorTraits;

// for methods
template<typename Return, typename Obj, typename... Args>
struct MakeFunctorTraits<Return (Obj::*)(Args...)> {
  using RunType = Return(Obj*, Args...);
  using ReturnType = Return;
};

// for functions
template<typename Return, typename... Args>
struct MakeFunctorTraits<Return(*)(Args...)> {
  using RunType = Return(Args...);
  using ReturnType = Return;
};



template<size_t ...>
struct ArgSeq {};

template<size_t N, size_t... S>
struct GenSeq : GenSeq<N - 1, N - 1, S...> {};

template<size_t... S>
struct GenSeq<0, S...> {
  typedef ArgSeq<S...> type;
};

template<typename R, typename T>
struct Expander;

template<typename R, typename... Args>
struct Expander<R, std::tuple<Args...>> {
  static R Expand(void *functor, std::tuple<Args...> args) {
    return ExpandInternal(
      reinterpret_cast<R(*)(Args...)>(functor),
      std::move(args),
      typename GenSeq<sizeof...(Args)>::type());
  }

  template<size_t... S>
  static R ExpandInternal(
      R(*method)(Args...),
      std::tuple<Args...> args,
      ArgSeq<S...>) {
    return method(std::move(std::get<S>(args))...);
  }
};

template<typename Return, typename... Needed>
class InvokerBase {
 public:
  virtual Return Invoke(Needed... args) = 0;
};

template<typename Return, typename BoundTuple, typename... Needed>
class Invoker : public InvokerBase<Return, Needed...> {
 public:
  Invoker(void *functor, BoundTuple bound) {
    functor_ = functor;
    bound_ = bound;
  }

  Return Invoke(Needed... args) {
    auto new_args = std::make_tuple(std::forward<Needed>(args)...);
    auto all_args = std::tuple_cat(bound_, std::move(new_args));
    return InvokeInternal(std::move(all_args));
  }

 private:
  void *functor_;
  BoundTuple bound_;

  template<typename ...All>
  Return InvokeInternal(std::tuple<All...> arguments) {
    return Expander<Return, std::tuple<All...>>::Expand(
      functor_, std::move(arguments));
  }
};

template<typename R, typename T, typename List>
struct MakeInvokerTypeImpl;

template<typename R, typename T, typename... Args>
struct MakeInvokerTypeImpl<R, T, TypeList<Args...>> {
  using Type = Invoker<R, T, Args...>;
};

template<typename R, typename T, typename ArgList>
using MakeInvokerType = typename MakeInvokerTypeImpl<R, T, ArgList>::Type;

template<typename Functor, typename... Bound>
struct BindHelper {
  static constexpr size_t num_bound = sizeof...(Bound);
  using FunctorTraits = MakeFunctorTraits<Functor>;

  using RunType = typename FunctorTraits::RunType;
  using ReturnType = ExtractReturn<RunType>;
  using RunParams = ExtractArgs<RunType>;

  using BoundParams = typename TakeTypeListImpl<num_bound, RunParams>::Type;
  using BoundTuple = typename TakeTypeListImpl<num_bound, RunParams>::TupleType;
  using UnboundParams = typename DropTypeListImpl<num_bound, RunParams>::Type;
  using BoundArguments = TypeList<Bound...>;
  using UnboundRunType = MakeFunctionType<ReturnType, UnboundParams>;

  using InvokerType = MakeInvokerType<ReturnType, BoundTuple, UnboundParams>;
};

template<typename Functor, typename... Bound>
using UnboundRunType = typename BindHelper<Functor, Bound...>::UnboundRunType;

template<typename Functor>
using ReturnType = ExtractReturn<typename MakeFunctorTraits<Functor>::RunType>;

template<typename Functor, typename... Bound>
using BoundTupleArgs = typename BindHelper<Functor, Bound...>::BoundTuple;

template<typename Functor, typename... Bound>
using InvokerType = typename BindHelper<Functor, Bound...>::InvokerType;

template<typename Signature>
class Callback;

template<typename T>
struct CallbackDefaultConstruct {
  static T Construct() { return {}; }
};

template<>
struct CallbackDefaultConstruct<void> {
  static void Construct() {}
};

template<typename R, typename... Args>
class Callback<R(Args...)> {
 private:
  std::unique_ptr<InvokerBase<R, Args...>> invoker_;
  Location bound_at_;

 public:
  Callback(std::unique_ptr<InvokerBase<R, Args...>> invoker,
           Location bound_at) : invoker_(std::move(invoker)),
                                bound_at_(bound_at) {}

  Callback() : bound_at_(Location::Current()) {
    invoker_ = nullptr;
  }

  R Run(Args... args) {
    if (!invoker_)
      return CallbackDefaultConstruct<R>::Construct();
    return invoker_->Invoke(std::forward<Args>(args)...);
  }

  Location GetSource() {
    return bound_at_;
  }
};

template<typename Functor, typename... Bound>
inline Callback<UnboundRunType<Functor, Bound...>> Bind(
    Functor&& functor, Bound&&... args) {

  // TODO replace Invoker<ReturnType<Functor>> with a handler for binding binds.
  auto invoker = std::make_unique<InvokerType<Functor, Bound...>>(
    reinterpret_cast<void *>(functor),
    std::make_tuple(std::forward<Bound>(args)...));

  return Callback<UnboundRunType<Functor, Bound...>>(
    std::move(invoker), Location::Current());
}

template<typename Functor>
inline Callback<UnboundRunType<Functor>> Bind(
    Functor&& functor, Location loc=Location::Current()) {
  auto invoker = std::make_unique<InvokerType<Functor>>(
    reinterpret_cast<void *>(functor), std::make_tuple());

  return Callback<UnboundRunType<Functor>>(std::move(invoker), loc);
}



}  // namespace util

#endif
