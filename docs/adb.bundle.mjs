var __defProp = Object.defineProperty;
var __typeError = (msg) => {
  throw TypeError(msg);
};
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
var __accessCheck = (obj, member, msg) => member.has(obj) || __typeError("Cannot " + msg);
var __privateGet = (obj, member, getter) => (__accessCheck(obj, member, "read from private field"), getter ? getter.call(obj) : member.get(obj));
var __privateAdd = (obj, member, value) => member.has(obj) ? __typeError("Cannot add the same private member more than once") : member instanceof WeakSet ? member.add(obj) : member.set(obj, value);
var __privateSet = (obj, member, value, setter) => (__accessCheck(obj, member, "write to private field"), setter ? setter.call(obj, value) : member.set(obj, value), value);
var __privateMethod = (obj, member, method) => (__accessCheck(obj, member, "access private method"), method);

// node_modules/@yume-chan/async/esm/promise-resolver.js
var _promise, _resolve, _reject, _state;
var PromiseResolver = class {
  constructor() {
    __privateAdd(this, _promise);
    __privateAdd(this, _resolve);
    __privateAdd(this, _reject);
    __privateAdd(this, _state, "running");
    __publicField(this, "resolve", (value) => {
      __privateGet(this, _resolve).call(this, value);
      __privateSet(this, _state, "resolved");
    });
    __publicField(this, "reject", (reason) => {
      __privateGet(this, _reject).call(this, reason);
      __privateSet(this, _state, "rejected");
    });
    __privateSet(this, _promise, new Promise((resolve, reject) => {
      __privateSet(this, _resolve, resolve);
      __privateSet(this, _reject, reject);
    }));
  }
  get promise() {
    return __privateGet(this, _promise);
  }
  get state() {
    return __privateGet(this, _state);
  }
};
_promise = new WeakMap();
_resolve = new WeakMap();
_reject = new WeakMap();
_state = new WeakMap();

// node_modules/@yume-chan/async/esm/async-operation-manager.js
var AsyncOperationManager = class {
  constructor(startId = 0) {
    __publicField(this, "nextId");
    __publicField(this, "pendingResolvers", /* @__PURE__ */ new Map());
    this.nextId = startId;
  }
  add() {
    const id = this.nextId++;
    const resolver = new PromiseResolver();
    this.pendingResolvers.set(id, resolver);
    return [id, resolver.promise];
  }
  getResolver(id) {
    if (!this.pendingResolvers.has(id)) {
      return null;
    }
    const resolver = this.pendingResolvers.get(id);
    this.pendingResolvers.delete(id);
    return resolver;
  }
  resolve(id, result) {
    const resolver = this.getResolver(id);
    if (resolver !== null) {
      resolver.resolve(result);
      return true;
    }
    return false;
  }
  reject(id, reason) {
    const resolver = this.getResolver(id);
    if (resolver !== null) {
      resolver.reject(reason);
      return true;
    }
    return false;
  }
};

// node_modules/@yume-chan/async/esm/delay.js
function delay(time) {
  return new Promise((resolve) => {
    globalThis.setTimeout(() => resolve(), time);
  });
}

// node_modules/@yume-chan/async/esm/maybe-promise.js
function isPromiseLike(value) {
  return typeof value === "object" && value !== null && "then" in value;
}

// node_modules/@yume-chan/struct/esm/bipedal.js
function advance(iterator, next) {
  while (true) {
    const { done, value } = iterator.next(next);
    if (done) {
      return value;
    }
    if (isPromiseLike(value)) {
      return value.then((value2) => advance(iterator, { resolved: value2 }), (error) => advance(iterator, { error }));
    }
    next = value;
  }
}
// @__NO_SIDE_EFFECTS__
function bipedal(fn, bindThis) {
  function result(...args) {
    const iterator = fn.call(this, function* (value) {
      if (isPromiseLike(value)) {
        const result2 = yield value;
        if ("resolved" in result2) {
          return result2.resolved;
        } else {
          throw result2.error;
        }
      }
      return value;
    }, ...args);
    return advance(iterator, void 0);
  }
  if (bindThis) {
    return result.bind(bindThis);
  } else {
    return result;
  }
}

// node_modules/@yume-chan/struct/esm/field/serialize.js
function defaultFieldSerializer(serializer) {
  return (source, context) => {
    if ("buffer" in context) {
      const buffer2 = serializer(source, context);
      context.buffer.set(buffer2, context.index);
      return buffer2.length;
    } else {
      return serializer(source, context);
    }
  };
}
function byobFieldSerializer(size, serializer) {
  return (source, context) => {
    if ("buffer" in context) {
      context.index ?? (context.index = 0);
      serializer(source, context);
      return size;
    } else {
      const buffer2 = new Uint8Array(size);
      serializer(source, {
        buffer: buffer2,
        index: 0,
        littleEndian: context.littleEndian
      });
      return buffer2;
    }
  };
}

// node_modules/@yume-chan/struct/esm/field/factory.js
// @__NO_SIDE_EFFECTS__
function _field(size, type, serialize, deserialize, options) {
  const field2 = {
    size,
    type,
    serialize: type === "default" ? defaultFieldSerializer(serialize) : byobFieldSerializer(size, serialize),
    deserialize: bipedal(deserialize),
    omitInit: options?.omitInit
  };
  if (options?.init) {
    field2.init = options.init;
  }
  return field2;
}
var field = _field;

// node_modules/@yume-chan/struct/esm/buffer.js
var EmptyUint8Array = new Uint8Array(0);
function copyMaybeDifferentLength(dest, source, index, length) {
  if (source.length < length) {
    dest.set(source, index);
    dest.fill(0, index + source.length, index + length);
  } else if (source.length === length) {
    dest.set(source, index);
  } else {
    dest.set(source.subarray(0, length), index);
  }
}
// @__NO_SIDE_EFFECTS__
function buffer(lengthOrField, converter) {
  if (typeof lengthOrField === "number") {
    let serialize;
    let deserialize2;
    let init2;
    if (lengthOrField === 0) {
      serialize = () => {
      };
      if (converter) {
        deserialize2 = function* () {
          return converter.convert(EmptyUint8Array);
        };
      } else {
        deserialize2 = function* () {
          return EmptyUint8Array;
        };
      }
    } else {
      serialize = (value, { buffer: buffer2, index }) => copyMaybeDifferentLength(buffer2, value, index, lengthOrField);
      if (converter) {
        deserialize2 = function* (then, reader) {
          const array = reader.readExactly(lengthOrField);
          return converter.convert(yield* then(array));
        };
        init2 = (value) => converter.back(value);
      } else {
        deserialize2 = function* (_then, reader) {
          const array = reader.readExactly(lengthOrField);
          return array;
        };
      }
    }
    return field(lengthOrField, "byob", serialize, deserialize2, { init: init2 });
  }
  if ((typeof lengthOrField === "object" || typeof lengthOrField === "function") && "serialize" in lengthOrField) {
    let deserialize2;
    let init2;
    if (converter) {
      deserialize2 = function* (then, reader, context) {
        const length = yield* then(lengthOrField.deserialize(reader, context));
        const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
        return converter.convert(yield* then(array));
      };
      init2 = (value) => converter.back(value);
    } else {
      deserialize2 = function* (then, reader, context) {
        const length = yield* then(lengthOrField.deserialize(reader, context));
        const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
        return array;
      };
    }
    return field(lengthOrField.size, "default", (value, { littleEndian }) => {
      if (lengthOrField.type === "default") {
        const lengthBuffer = lengthOrField.serialize(value.length, {
          littleEndian
        });
        if (value.length === 0) {
          return lengthBuffer;
        }
        const result = new Uint8Array(lengthBuffer.length + value.length);
        result.set(lengthBuffer, 0);
        result.set(value, lengthBuffer.length);
        return result;
      } else {
        const result = new Uint8Array(lengthOrField.size + value.length);
        lengthOrField.serialize(value.length, {
          buffer: result,
          index: 0,
          littleEndian
        });
        result.set(value, lengthOrField.size);
        return result;
      }
    }, deserialize2, { init: init2 });
  }
  if (typeof lengthOrField === "string") {
    let deserialize2;
    let init2;
    if (converter) {
      deserialize2 = function* (then, reader, { dependencies }) {
        const length = dependencies[lengthOrField];
        const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
        return converter.convert(yield* then(array));
      };
      init2 = (value, dependencies) => {
        const array = converter.back(value);
        dependencies[lengthOrField] = array.length;
        return array;
      };
    } else {
      deserialize2 = function* (_then, reader, { dependencies }) {
        const length = dependencies[lengthOrField];
        const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
        return array;
      };
      init2 = (value, dependencies) => {
        const array = value;
        dependencies[lengthOrField] = array.length;
        return array;
      };
    }
    return field(0, "default", (source) => source, deserialize2, { init: init2 });
  }
  let deserialize;
  let init;
  if (converter) {
    deserialize = function* (then, reader, { dependencies }) {
      const rawLength = dependencies[lengthOrField.field];
      const length = lengthOrField.convert(rawLength);
      const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
      return converter.convert(yield* then(array));
    };
    init = (value, dependencies) => {
      const array = converter.back(value);
      dependencies[lengthOrField.field] = lengthOrField.back(array.length);
      return array;
    };
  } else {
    deserialize = function* (_then, reader, { dependencies }) {
      const rawLength = dependencies[lengthOrField.field];
      const length = lengthOrField.convert(rawLength);
      const array = length !== 0 ? reader.readExactly(length) : EmptyUint8Array;
      return array;
    };
    init = (value, dependencies) => {
      const array = value;
      dependencies[lengthOrField.field] = lengthOrField.back(array.length);
      return array;
    };
  }
  return field(0, "default", (source) => source, deserialize, { init });
}

// node_modules/@yume-chan/struct/esm/readable.js
var ExactReadableEndedError = class extends Error {
  constructor() {
    super("ExactReadable ended");
  }
};

// node_modules/@yume-chan/struct/esm/struct.js
var StructDeserializeError = class extends Error {
  constructor(message) {
    super(message);
  }
};
var StructNotEnoughDataError = class extends StructDeserializeError {
  constructor() {
    super("The underlying readable was ended before the struct was fully deserialized");
  }
};
var StructEmptyError = class extends StructDeserializeError {
  constructor() {
    super("The underlying readable doesn't contain any more struct");
  }
};
// @__NO_SIDE_EFFECTS__
function struct(fields, options) {
  const fieldList = Object.entries(fields);
  let size = 0;
  let byob = true;
  for (const [, field2] of fieldList) {
    size += field2.size;
    if (byob && field2.type !== "byob") {
      byob = false;
    }
  }
  const littleEndian = options.littleEndian;
  const extra = options.extra ? Object.getOwnPropertyDescriptors(options.extra) : void 0;
  return {
    littleEndian,
    fields,
    extra: options.extra,
    type: byob ? "byob" : "default",
    size,
    serialize(source, bufferOrContext) {
      const temp = { ...source };
      for (const [key, field2] of fieldList) {
        if (key in temp && "init" in field2) {
          const result = field2.init?.(temp[key], temp);
          temp[key] = result;
        }
      }
      const sizes = new Array(fieldList.length);
      const buffers = new Array(fieldList.length);
      {
        const context2 = { littleEndian };
        for (const [index2, [key, field2]] of fieldList.entries()) {
          if (field2.type === "byob") {
            sizes[index2] = field2.size;
          } else {
            buffers[index2] = field2.serialize(temp[key], context2);
            sizes[index2] = buffers[index2].length;
          }
        }
      }
      const size2 = sizes.reduce((sum, size3) => sum + size3, 0);
      let externalBuffer;
      let buffer2;
      let index;
      if (bufferOrContext instanceof Uint8Array) {
        if (bufferOrContext.length < size2) {
          throw new Error("Buffer too small");
        }
        externalBuffer = true;
        buffer2 = bufferOrContext;
        index = 0;
      } else if (typeof bufferOrContext === "object" && "buffer" in bufferOrContext) {
        externalBuffer = true;
        buffer2 = bufferOrContext.buffer;
        index = bufferOrContext.index ?? 0;
        if (buffer2.length - index < size2) {
          throw new Error("Buffer too small");
        }
      } else {
        externalBuffer = false;
        buffer2 = new Uint8Array(size2);
        index = 0;
      }
      const context = {
        buffer: buffer2,
        index,
        littleEndian
      };
      for (const [index2, [key, field2]] of fieldList.entries()) {
        if (buffers[index2]) {
          buffer2.set(buffers[index2], context.index);
        } else {
          field2.serialize(temp[key], context);
        }
        context.index += sizes[index2];
      }
      if (externalBuffer) {
        return size2;
      } else {
        return buffer2;
      }
    },
    deserialize: bipedal(function* (then, reader) {
      const startPosition = reader.position;
      const result = {};
      const context = {
        dependencies: result,
        littleEndian
      };
      try {
        for (const [key, field2] of fieldList) {
          result[key] = yield* then(field2.deserialize(reader, context));
        }
      } catch (e2) {
        if (!(e2 instanceof ExactReadableEndedError)) {
          throw e2;
        }
        if (reader.position === startPosition) {
          throw new StructEmptyError();
        } else {
          throw new StructNotEnoughDataError();
        }
      }
      if (extra) {
        Object.defineProperties(result, extra);
      }
      if (options.postDeserialize) {
        return options.postDeserialize.call(result, result);
      } else {
        return result;
      }
    })
  };
}

// node_modules/@yume-chan/struct/esm/extend.js
// @__NO_SIDE_EFFECTS__
function extend(base, fields, options) {
  return struct(Object.assign({}, base.fields, fields), {
    littleEndian: options?.littleEndian ?? base.littleEndian,
    extra: base.extra,
    postDeserialize: options?.postDeserialize
  });
}

// node_modules/@yume-chan/no-data-view/esm/int32.js
// @__NO_SIDE_EFFECTS__
function getInt32(buffer2, offset, littleEndian) {
  return littleEndian ? buffer2[offset] | buffer2[offset + 1] << 8 | buffer2[offset + 2] << 16 | buffer2[offset + 3] << 24 : buffer2[offset] << 24 | buffer2[offset + 1] << 16 | buffer2[offset + 2] << 8 | buffer2[offset + 3];
}
function setInt32(buffer2, offset, value, littleEndian) {
  if (littleEndian) {
    buffer2[offset] = value;
    buffer2[offset + 1] = value >> 8;
    buffer2[offset + 2] = value >> 16;
    buffer2[offset + 3] = value >> 24;
  } else {
    buffer2[offset] = value >> 24;
    buffer2[offset + 1] = value >> 16;
    buffer2[offset + 2] = value >> 8;
    buffer2[offset + 3] = value;
  }
}

// node_modules/@yume-chan/no-data-view/esm/int64.js
function setInt64LittleEndian(buffer2, offset, value) {
  buffer2[offset] = Number(value & 0xffn);
  buffer2[offset + 1] = Number(value >> 8n & 0xffn);
  buffer2[offset + 2] = Number(value >> 16n & 0xffn);
  buffer2[offset + 3] = Number(value >> 24n & 0xffn);
  buffer2[offset + 4] = Number(value >> 32n & 0xffn);
  buffer2[offset + 5] = Number(value >> 40n & 0xffn);
  buffer2[offset + 6] = Number(value >> 48n & 0xffn);
  buffer2[offset + 7] = Number(value >> 56n & 0xffn);
}
function setInt64BigEndian(buffer2, offset, value) {
  buffer2[offset] = Number(value >> 56n & 0xffn);
  buffer2[offset + 1] = Number(value >> 48n & 0xffn);
  buffer2[offset + 2] = Number(value >> 40n & 0xffn);
  buffer2[offset + 3] = Number(value >> 32n & 0xffn);
  buffer2[offset + 4] = Number(value >> 24n & 0xffn);
  buffer2[offset + 5] = Number(value >> 16n & 0xffn);
  buffer2[offset + 6] = Number(value >> 8n & 0xffn);
  buffer2[offset + 7] = Number(value & 0xffn);
}

// node_modules/@yume-chan/no-data-view/esm/uint32.js
// @__NO_SIDE_EFFECTS__
function getUint32LittleEndian(buffer2, offset) {
  return (buffer2[offset] | buffer2[offset + 1] << 8 | buffer2[offset + 2] << 16 | buffer2[offset + 3] << 24) >>> 0;
}
// @__NO_SIDE_EFFECTS__
function getUint32(buffer2, offset, littleEndian) {
  return littleEndian ? (buffer2[offset] | buffer2[offset + 1] << 8 | buffer2[offset + 2] << 16 | buffer2[offset + 3] << 24) >>> 0 : (buffer2[offset] << 24 | buffer2[offset + 1] << 16 | buffer2[offset + 2] << 8 | buffer2[offset + 3]) >>> 0;
}
function setUint32LittleEndian(buffer2, offset, value) {
  buffer2[offset] = value;
  buffer2[offset + 1] = value >> 8;
  buffer2[offset + 2] = value >> 16;
  buffer2[offset + 3] = value >> 24;
}
function setUint32(buffer2, offset, value, littleEndian) {
  if (littleEndian) {
    buffer2[offset] = value;
    buffer2[offset + 1] = value >> 8;
    buffer2[offset + 2] = value >> 16;
    buffer2[offset + 3] = value >> 24;
  } else {
    buffer2[offset] = value >> 24;
    buffer2[offset + 1] = value >> 16;
    buffer2[offset + 2] = value >> 8;
    buffer2[offset + 3] = value;
  }
}

// node_modules/@yume-chan/no-data-view/esm/uint64.js
function getUint64BigEndian(buffer2, offset) {
  return BigInt(buffer2[offset]) << 56n | BigInt(buffer2[offset + 1]) << 48n | BigInt(buffer2[offset + 2]) << 40n | BigInt(buffer2[offset + 3]) << 32n | BigInt(buffer2[offset + 4]) << 24n | BigInt(buffer2[offset + 5]) << 16n | BigInt(buffer2[offset + 6]) << 8n | BigInt(buffer2[offset + 7]);
}
function getUint64(buffer2, offset, littleEndian) {
  return littleEndian ? BigInt(buffer2[offset]) | BigInt(buffer2[offset + 1]) << 8n | BigInt(buffer2[offset + 2]) << 16n | BigInt(buffer2[offset + 3]) << 24n | BigInt(buffer2[offset + 4]) << 32n | BigInt(buffer2[offset + 5]) << 40n | BigInt(buffer2[offset + 6]) << 48n | BigInt(buffer2[offset + 7]) << 56n : BigInt(buffer2[offset]) << 56n | BigInt(buffer2[offset + 1]) << 48n | BigInt(buffer2[offset + 2]) << 40n | BigInt(buffer2[offset + 3]) << 32n | BigInt(buffer2[offset + 4]) << 24n | BigInt(buffer2[offset + 5]) << 16n | BigInt(buffer2[offset + 6]) << 8n | BigInt(buffer2[offset + 7]);
}
function setUint64(buffer2, offset, value, littleEndian) {
  if (littleEndian) {
    buffer2[offset] = Number(value & 0xffn);
    buffer2[offset + 1] = Number(value >> 8n & 0xffn);
    buffer2[offset + 2] = Number(value >> 16n & 0xffn);
    buffer2[offset + 3] = Number(value >> 24n & 0xffn);
    buffer2[offset + 4] = Number(value >> 32n & 0xffn);
    buffer2[offset + 5] = Number(value >> 40n & 0xffn);
    buffer2[offset + 6] = Number(value >> 48n & 0xffn);
    buffer2[offset + 7] = Number(value >> 56n & 0xffn);
  } else {
    buffer2[offset] = Number(value >> 56n & 0xffn);
    buffer2[offset + 1] = Number(value >> 48n & 0xffn);
    buffer2[offset + 2] = Number(value >> 40n & 0xffn);
    buffer2[offset + 3] = Number(value >> 32n & 0xffn);
    buffer2[offset + 4] = Number(value >> 24n & 0xffn);
    buffer2[offset + 5] = Number(value >> 16n & 0xffn);
    buffer2[offset + 6] = Number(value >> 8n & 0xffn);
    buffer2[offset + 7] = Number(value & 0xffn);
  }
}

// node_modules/@yume-chan/struct/esm/number.js
// @__NO_SIDE_EFFECTS__
function number(size, serialize, deserialize) {
  const fn = (() => fn);
  Object.assign(fn, field(size, "byob", serialize, deserialize));
  return fn;
}
var u8 = /* @__PURE__ */ number(1, (value, { buffer: buffer2, index }) => {
  buffer2[index] = value;
}, function* (then, reader) {
  const data = yield* then(reader.readExactly(1));
  return data[0];
});
var u32 = /* @__PURE__ */ number(4, (value, { buffer: buffer2, index, littleEndian }) => {
  setUint32(buffer2, index, value, littleEndian);
}, function* (then, reader, { littleEndian }) {
  const data = yield* then(reader.readExactly(4));
  return getUint32(data, 0, littleEndian);
});
var s32 = /* @__PURE__ */ number(4, (value, { buffer: buffer2, index, littleEndian }) => {
  setInt32(buffer2, index, value, littleEndian);
}, function* (then, reader, { littleEndian }) {
  const data = yield* then(reader.readExactly(4));
  return getInt32(data, 0, littleEndian);
});
var u64 = /* @__PURE__ */ number(8, (value, { buffer: buffer2, index, littleEndian }) => {
  setUint64(buffer2, index, value, littleEndian);
}, function* (then, reader, { littleEndian }) {
  const data = yield* then(reader.readExactly(8));
  return getUint64(data, 0, littleEndian);
});

// node_modules/@yume-chan/struct/esm/utils.js
var { TextEncoder, TextDecoder } = globalThis;
var SharedEncoder = /* @__PURE__ */ new TextEncoder();
var SharedDecoder = /* @__PURE__ */ new TextDecoder();
// @__NO_SIDE_EFFECTS__
function encodeUtf8(input) {
  return SharedEncoder.encode(input);
}
// @__NO_SIDE_EFFECTS__
function decodeUtf8(buffer2) {
  return SharedDecoder.decode(buffer2);
}

// node_modules/@yume-chan/struct/esm/string.js
var string = (/* @__NO_SIDE_EFFECTS__ */ (lengthOrField) => {
  const field2 = buffer(lengthOrField, {
    convert: decodeUtf8,
    back: encodeUtf8
  });
  field2.as = () => field2;
  return field2;
});

// node_modules/@yume-chan/stream-extra/esm/stream.js
var { AbortController: AbortController2 } = globalThis;
var ReadableStream = /* @__PURE__ */ (() => {
  const { ReadableStream: ReadableStream4 } = globalThis;
  if (!ReadableStream4.from) {
    ReadableStream4.from = function(iterable) {
      const iterator = Symbol.asyncIterator in iterable ? iterable[Symbol.asyncIterator]() : iterable[Symbol.iterator]();
      return new ReadableStream4({
        async pull(controller) {
          const result = await iterator.next();
          if (result.done) {
            controller.close();
            return;
          }
          controller.enqueue(result.value);
        },
        async cancel(reason) {
          await iterator.return?.(reason);
        }
      });
    };
  }
  if (!ReadableStream4.prototype[Symbol.asyncIterator] || !ReadableStream4.prototype.values) {
    ReadableStream4.prototype.values = async function* (options) {
      const reader = this.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            return;
          }
          yield value;
        }
      } finally {
        if (!options?.preventCancel) {
          await reader.cancel();
        }
        reader.releaseLock();
      }
    };
    ReadableStream4.prototype[Symbol.asyncIterator] = // eslint-disable-next-line @typescript-eslint/unbound-method
    ReadableStream4.prototype.values;
  }
  return ReadableStream4;
})();
var { WritableStream, TransformStream } = globalThis;

// node_modules/@yume-chan/stream-extra/esm/task-queue.js
var _ready, _disposed;
var TaskQueue = class {
  constructor() {
    __privateAdd(this, _ready);
    __privateAdd(this, _disposed, false);
  }
  enqueue(task, bail = false) {
    if (__privateGet(this, _disposed)) {
      throw new Error("TaskQueue is disposed");
    }
    if (!__privateGet(this, _ready)) {
      try {
        const result2 = task();
        if (isPromiseLike(result2)) {
          __privateSet(this, _ready, result2.then(() => {
          }, (e2) => {
            if (bail) {
              throw e2;
            }
          }));
        }
        return result2;
      } catch (e2) {
        if (bail) {
          const promise = Promise.reject(e2);
          void promise.catch(() => {
          });
          __privateSet(this, _ready, promise);
        }
        throw e2;
      }
    }
    const result = __privateGet(this, _ready).then(() => {
      if (__privateGet(this, _disposed)) {
        throw new Error("TaskQueue is disposed");
      }
      return task();
    });
    __privateSet(this, _ready, result.then(() => {
    }, (e2) => {
      if (bail || __privateGet(this, _disposed)) {
        throw e2;
      }
    }));
    return result;
  }
  dispose() {
    __privateSet(this, _disposed, true);
  }
};
_ready = new WeakMap();
_disposed = new WeakMap();

// node_modules/@yume-chan/stream-extra/esm/push-readable.js
var PushReadableStream = class extends ReadableStream {
  /**
   * Create a new `PushReadableStream` from a source.
   *
   * @param source If `source` returns a `Promise`, the stream will be closed
   * when the `Promise` is resolved, and be errored when the `Promise` is rejected.
   * @param strategy
   */
  constructor(source, strategy, logger) {
    let controller;
    const tasks = new TaskQueue();
    let zeroHighWaterMarkAllowEnqueue = false;
    let waterMarkLow;
    const abortController = new AbortController2();
    let stopped = false;
    const enqueue2 = (chunk) => {
      logger?.({
        source: "producer",
        operation: "enqueue",
        value: chunk,
        phase: "start"
      });
      if (abortController.signal.aborted) {
        logger?.({
          source: "producer",
          operation: "enqueue",
          value: chunk,
          phase: "ignored"
        });
        return false;
      }
      if (controller.desiredSize === null) {
        controller.enqueue(chunk);
        throw new Error("unreachable");
      }
      if (zeroHighWaterMarkAllowEnqueue) {
        zeroHighWaterMarkAllowEnqueue = false;
        controller.enqueue(chunk);
        logger?.({
          source: "producer",
          operation: "enqueue",
          value: chunk,
          phase: "complete"
        });
        return true;
      }
      if (controller.desiredSize <= 0) {
        logger?.({
          source: "producer",
          operation: "enqueue",
          value: chunk,
          phase: "waiting"
        });
        waterMarkLow = new PromiseResolver();
        return waterMarkLow.promise.then(() => {
          controller.enqueue(chunk);
          logger?.({
            source: "producer",
            operation: "enqueue",
            value: chunk,
            phase: "complete"
          });
          return true;
        }, () => {
          logger?.({
            source: "producer",
            operation: "enqueue",
            value: chunk,
            phase: "ignored"
          });
          return false;
        });
      }
      controller.enqueue(chunk);
      logger?.({
        source: "producer",
        operation: "enqueue",
        value: chunk,
        phase: "complete"
      });
      return true;
    };
    const close = (explicit) => {
      logger?.({
        source: "producer",
        operation: "close",
        explicit,
        phase: "start"
      });
      if (abortController.signal.aborted || stopped && !explicit) {
        logger?.({
          source: "producer",
          operation: "close",
          explicit,
          phase: "ignored"
        });
        return;
      }
      controller.close();
      stopped = true;
      waterMarkLow?.reject();
      logger?.({
        source: "producer",
        operation: "close",
        explicit,
        phase: "complete"
      });
    };
    const error = (error2, explicit) => {
      logger?.({
        source: "producer",
        operation: "error",
        explicit,
        phase: "start"
      });
      stopped = true;
      controller.error(error2);
      waterMarkLow?.reject();
      logger?.({
        source: "producer",
        operation: "error",
        explicit,
        phase: "complete"
      });
    };
    super({
      start: (controller_) => {
        controller = controller_;
        const result = source({
          abortSignal: abortController.signal,
          enqueue: async (chunk) => (
            // Run `enqueue`s in serial
            // Use `async/await` to always return a `Promise`
            await tasks.enqueue(() => enqueue2(chunk))
          ),
          close() {
            close(true);
          },
          error(e2) {
            error(e2, true);
          }
        });
        if (!stopped && isPromiseLike(result)) {
          result.then(() => close(false), (e2) => error(e2, false));
        }
      },
      pull: () => {
        logger?.({
          source: "consumer",
          operation: "pull",
          phase: "start"
        });
        if (waterMarkLow) {
          waterMarkLow.resolve(void 0);
          waterMarkLow = void 0;
        } else if (strategy?.highWaterMark === 0) {
          zeroHighWaterMarkAllowEnqueue = true;
        }
        logger?.({
          source: "consumer",
          operation: "pull",
          phase: "complete"
        });
      },
      cancel: (reason) => {
        logger?.({
          source: "consumer",
          operation: "cancel",
          phase: "start"
        });
        stopped = true;
        abortController.abort(reason);
        waterMarkLow?.reject();
        logger?.({
          source: "consumer",
          operation: "cancel",
          phase: "complete"
        });
      }
    }, strategy);
  }
};

// node_modules/@yume-chan/stream-extra/esm/try-close.js
async function tryCancel(stream) {
  try {
    await stream.cancel();
    return true;
  } catch {
    return false;
  }
}

// node_modules/@yume-chan/stream-extra/esm/buffered.js
var _buffered, _bufferedOffset, _bufferedLength, _position, _BufferedReadableStream_instances, readBuffered_fn, readSource_fn;
var BufferedReadableStream = class {
  constructor(stream) {
    __privateAdd(this, _BufferedReadableStream_instances);
    __privateAdd(this, _buffered);
    // PERF: `subarray` is slow
    // don't use it until absolutely necessary
    __privateAdd(this, _bufferedOffset, 0);
    __privateAdd(this, _bufferedLength, 0);
    __privateAdd(this, _position, 0);
    __publicField(this, "stream");
    __publicField(this, "reader");
    __publicField(this, "readExactly", bipedal(function* (then, length) {
      let result;
      let index = 0;
      const initial = __privateMethod(this, _BufferedReadableStream_instances, readBuffered_fn).call(this, length);
      if (initial) {
        if (initial.length === length) {
          return initial;
        }
        result = new Uint8Array(length);
        result.set(initial, index);
        index += initial.length;
        length -= initial.length;
      } else {
        result = new Uint8Array(length);
      }
      while (length > 0) {
        const value = yield* then(__privateMethod(this, _BufferedReadableStream_instances, readSource_fn).call(this, length));
        result.set(value, index);
        index += value.length;
        length -= value.length;
      }
      return result;
    }));
    this.stream = stream;
    this.reader = stream.getReader();
  }
  get position() {
    return __privateGet(this, _position);
  }
  iterateExactly(length) {
    let state = __privateGet(this, _buffered) ? 0 : 1;
    return {
      next: () => {
        switch (state) {
          case 0: {
            const value = __privateMethod(this, _BufferedReadableStream_instances, readBuffered_fn).call(this, length);
            if (value.length === length) {
              state = 2;
            } else {
              length -= value.length;
              state = 1;
            }
            return { done: false, value };
          }
          case 1:
            state = 3;
            return {
              done: false,
              value: __privateMethod(this, _BufferedReadableStream_instances, readSource_fn).call(this, length).then((value) => {
                if (value.length === length) {
                  state = 2;
                } else {
                  length -= value.length;
                  state = 1;
                }
                return value;
              })
            };
          case 2:
            return { done: true, value: void 0 };
          case 3:
            throw new Error("Can't call `next` before previous Promise resolves");
          default:
            throw new Error("unreachable");
        }
      }
    };
  }
  /**
   * Return a readable stream with unconsumed data (if any) and
   * all data from the wrapped stream.
   * @returns A `ReadableStream`
   */
  release() {
    if (__privateGet(this, _bufferedLength) > 0) {
      return new PushReadableStream(async (controller) => {
        const buffered = __privateGet(this, _buffered).subarray(__privateGet(this, _bufferedOffset));
        await controller.enqueue(buffered);
        controller.abortSignal.addEventListener("abort", () => {
          void tryCancel(this.reader);
        });
        while (true) {
          const { done, value } = await this.reader.read();
          if (done) {
            return;
          }
          await controller.enqueue(value);
        }
      });
    } else {
      this.reader.releaseLock();
      return this.stream;
    }
  }
  async cancel(reason) {
    await this.reader.cancel(reason);
  }
};
_buffered = new WeakMap();
_bufferedOffset = new WeakMap();
_bufferedLength = new WeakMap();
_position = new WeakMap();
_BufferedReadableStream_instances = new WeakSet();
readBuffered_fn = function(length) {
  if (!__privateGet(this, _buffered)) {
    return void 0;
  }
  const value = __privateGet(this, _buffered).subarray(__privateGet(this, _bufferedOffset), __privateGet(this, _bufferedOffset) + length);
  if (__privateGet(this, _bufferedLength) > length) {
    __privateSet(this, _position, __privateGet(this, _position) + length);
    __privateSet(this, _bufferedOffset, __privateGet(this, _bufferedOffset) + length);
    __privateSet(this, _bufferedLength, __privateGet(this, _bufferedLength) - length);
    return value;
  }
  __privateSet(this, _position, __privateGet(this, _position) + __privateGet(this, _bufferedLength));
  __privateSet(this, _buffered, void 0);
  __privateSet(this, _bufferedOffset, 0);
  __privateSet(this, _bufferedLength, 0);
  return value;
};
readSource_fn = async function(length) {
  const { done, value } = await this.reader.read();
  if (done) {
    throw new ExactReadableEndedError();
  }
  if (value.length > length) {
    __privateSet(this, _buffered, value);
    __privateSet(this, _bufferedOffset, length);
    __privateSet(this, _bufferedLength, value.length - length);
    __privateSet(this, _position, __privateGet(this, _position) + length);
    return value.subarray(0, length);
  }
  __privateSet(this, _position, __privateGet(this, _position) + value.length);
  return value;
};

// node_modules/@yume-chan/stream-extra/esm/buffered-transform.js
var _readable, _writable;
var BufferedTransformStream = class {
  constructor(transform) {
    __privateAdd(this, _readable);
    __privateAdd(this, _writable);
    let bufferedStreamController;
    let writableStreamController;
    const buffered = new BufferedReadableStream(new PushReadableStream((controller) => {
      bufferedStreamController = controller;
    }));
    __privateSet(this, _readable, new ReadableStream({
      async pull(controller) {
        try {
          const value = await transform(buffered);
          controller.enqueue(value);
        } catch (e2) {
          if (e2 instanceof StructEmptyError) {
            controller.close();
            return;
          }
          throw e2;
        }
      },
      cancel: (reason) => {
        return writableStreamController.error(reason);
      }
    }));
    __privateSet(this, _writable, new WritableStream({
      start(controller) {
        writableStreamController = controller;
      },
      async write(chunk) {
        await bufferedStreamController.enqueue(chunk);
      },
      abort() {
        bufferedStreamController.close();
      },
      close() {
        bufferedStreamController.close();
      }
    }));
  }
  get readable() {
    return __privateGet(this, _readable);
  }
  get writable() {
    return __privateGet(this, _writable);
  }
};
_readable = new WeakMap();
_writable = new WeakMap();

// node_modules/@yume-chan/stream-extra/esm/concat.js
var _result, _resolver, _writable2, _readableController, _readable2;
var ConcatStringStream = class {
  constructor() {
    // PERF: rope (concat strings) is faster than `[].join('')`
    __privateAdd(this, _result, "");
    __privateAdd(this, _resolver, new PromiseResolver());
    __privateAdd(this, _writable2, new WritableStream({
      write: (chunk) => {
        __privateSet(this, _result, __privateGet(this, _result) + chunk);
      },
      close: () => {
        __privateGet(this, _resolver).resolve(__privateGet(this, _result));
        __privateGet(this, _readableController).enqueue(__privateGet(this, _result));
        __privateGet(this, _readableController).close();
      },
      abort: (reason) => {
        __privateGet(this, _resolver).reject(reason);
        __privateGet(this, _readableController).error(reason);
      }
    }));
    __privateAdd(this, _readableController);
    __privateAdd(this, _readable2, new ReadableStream({
      start: (controller) => {
        __privateSet(this, _readableController, controller);
      }
    }));
    void Object.defineProperties(__privateGet(this, _readable2), {
      then: {
        get: () => __privateGet(this, _resolver).promise.then.bind(__privateGet(this, _resolver).promise)
      },
      catch: {
        get: () => __privateGet(this, _resolver).promise.catch.bind(__privateGet(this, _resolver).promise)
      },
      finally: {
        get: () => __privateGet(this, _resolver).promise.finally.bind(__privateGet(this, _resolver).promise)
      }
    });
  }
  get writable() {
    return __privateGet(this, _writable2);
  }
  get readable() {
    return __privateGet(this, _readable2);
  }
};
_result = new WeakMap();
_resolver = new WeakMap();
_writable2 = new WeakMap();
_readableController = new WeakMap();
_readable2 = new WeakMap();
var _segments, _resolver2, _writable3, _readableController2, _readable3;
var ConcatBufferStream = class {
  constructor() {
    __privateAdd(this, _segments, []);
    __privateAdd(this, _resolver2, new PromiseResolver());
    __privateAdd(this, _writable3, new WritableStream({
      write: (chunk) => {
        __privateGet(this, _segments).push(chunk);
      },
      close: () => {
        let result;
        let offset = 0;
        switch (__privateGet(this, _segments).length) {
          case 0:
            result = EmptyUint8Array;
            break;
          case 1:
            result = __privateGet(this, _segments)[0];
            break;
          default:
            result = new Uint8Array(__privateGet(this, _segments).reduce((prev, item) => prev + item.length, 0));
            for (const segment of __privateGet(this, _segments)) {
              result.set(segment, offset);
              offset += segment.length;
            }
            break;
        }
        __privateGet(this, _resolver2).resolve(result);
        __privateGet(this, _readableController2).enqueue(result);
        __privateGet(this, _readableController2).close();
      },
      abort: (reason) => {
        __privateGet(this, _resolver2).reject(reason);
        __privateGet(this, _readableController2).error(reason);
      }
    }));
    __privateAdd(this, _readableController2);
    __privateAdd(this, _readable3, new ReadableStream({
      start: (controller) => {
        __privateSet(this, _readableController2, controller);
      }
    }));
    void Object.defineProperties(__privateGet(this, _readable3), {
      then: {
        get: () => __privateGet(this, _resolver2).promise.then.bind(__privateGet(this, _resolver2).promise)
      },
      catch: {
        get: () => __privateGet(this, _resolver2).promise.catch.bind(__privateGet(this, _resolver2).promise)
      },
      finally: {
        get: () => __privateGet(this, _resolver2).promise.finally.bind(__privateGet(this, _resolver2).promise)
      }
    });
  }
  get writable() {
    return __privateGet(this, _writable3);
  }
  get readable() {
    return __privateGet(this, _readable3);
  }
};
_segments = new WeakMap();
_resolver2 = new WeakMap();
_writable3 = new WeakMap();
_readableController2 = new WeakMap();
_readable3 = new WeakMap();

// node_modules/@yume-chan/stream-extra/esm/consumable/readable.js
var ConsumableReadableStream = class _ConsumableReadableStream extends ReadableStream {
  static async enqueue(controller, chunk) {
    const output = new Consumable(chunk);
    controller.enqueue(output);
    await output.consumed;
  }
  constructor(source, strategy) {
    let wrappedController;
    let wrappedStrategy;
    if (strategy) {
      wrappedStrategy = {};
      if ("highWaterMark" in strategy) {
        wrappedStrategy.highWaterMark = strategy.highWaterMark;
      }
      if ("size" in strategy) {
        wrappedStrategy.size = (chunk) => {
          return strategy.size(chunk.value);
        };
      }
    }
    super({
      start(controller) {
        wrappedController = {
          enqueue(chunk) {
            return _ConsumableReadableStream.enqueue(controller, chunk);
          },
          close() {
            controller.close();
          },
          error(reason) {
            controller.error(reason);
          }
        };
        return source.start?.(wrappedController);
      },
      pull() {
        return source.pull?.(wrappedController);
      },
      cancel(reason) {
        return source.cancel?.(reason);
      }
    }, wrappedStrategy);
  }
};

// node_modules/@yume-chan/stream-extra/esm/consumable/wrap-byte-readable.js
var ConsumableWrapByteReadableStream = class extends ReadableStream {
  constructor(stream, chunkSize, min) {
    const reader = stream.getReader({ mode: "byob" });
    let array = new Uint8Array(chunkSize);
    super({
      async pull(controller) {
        const { done, value } = await reader.read(array, { min });
        if (done) {
          controller.close();
          return;
        }
        await ConsumableReadableStream.enqueue(controller, value);
        array = new Uint8Array(value.buffer);
      },
      cancel(reason) {
        return reader.cancel(reason);
      }
    });
  }
};

// node_modules/@yume-chan/stream-extra/esm/consumable/wrap-writable.js
var ConsumableWrapWritableStream = class extends WritableStream {
  constructor(stream) {
    const writer = stream.getWriter();
    super({
      write(chunk) {
        return chunk.tryConsume((chunk2) => writer.write(chunk2));
      },
      abort(reason) {
        return writer.abort(reason);
      },
      close() {
        return writer.close();
      }
    });
  }
};

// node_modules/@yume-chan/stream-extra/esm/consumable/writable.js
var ConsumableWritableStream = class extends WritableStream {
  static async write(writer, value) {
    const consumable = new Consumable(value);
    await writer.write(consumable);
    await consumable.consumed;
  }
  constructor(sink, strategy) {
    let wrappedStrategy;
    if (strategy) {
      wrappedStrategy = {};
      if ("highWaterMark" in strategy) {
        wrappedStrategy.highWaterMark = strategy.highWaterMark;
      }
      if ("size" in strategy) {
        wrappedStrategy.size = (chunk) => {
          return strategy.size(chunk instanceof Consumable ? chunk.value : chunk);
        };
      }
    }
    super({
      start(controller) {
        return sink.start?.(controller);
      },
      write(chunk, controller) {
        return chunk.tryConsume((chunk2) => sink.write?.(chunk2, controller));
      },
      abort(reason) {
        return sink.abort?.(reason);
      },
      close() {
        return sink.close?.();
      }
    }, wrappedStrategy);
  }
};

// node_modules/@yume-chan/stream-extra/esm/task.js
var { console } = globalThis;
var createTask = /* @__PURE__ */ (() => console?.createTask?.bind(console) ?? (() => ({
  run(callback) {
    return callback();
  }
})))();

// node_modules/@yume-chan/stream-extra/esm/consumable.js
var _task, _resolver3;
var Consumable = class {
  constructor(value) {
    __privateAdd(this, _task);
    __privateAdd(this, _resolver3);
    __publicField(this, "value");
    __publicField(this, "consumed");
    __privateSet(this, _task, createTask("Consumable"));
    this.value = value;
    __privateSet(this, _resolver3, new PromiseResolver());
    this.consumed = __privateGet(this, _resolver3).promise;
  }
  consume() {
    __privateGet(this, _resolver3).resolve();
  }
  error(error) {
    __privateGet(this, _resolver3).reject(error);
  }
  tryConsume(callback) {
    try {
      let result = __privateGet(this, _task).run(() => callback(this.value));
      if (isPromiseLike(result)) {
        result = result.then((value) => {
          __privateGet(this, _resolver3).resolve();
          return value;
        }, (e2) => {
          __privateGet(this, _resolver3).reject(e2);
          throw e2;
        });
      } else {
        __privateGet(this, _resolver3).resolve();
      }
      return result;
    } catch (e2) {
      __privateGet(this, _resolver3).reject(e2);
      throw e2;
    }
  }
};
_task = new WeakMap();
_resolver3 = new WeakMap();
__publicField(Consumable, "WritableStream", ConsumableWritableStream);
__publicField(Consumable, "WrapWritableStream", ConsumableWrapWritableStream);
__publicField(Consumable, "ReadableStream", ConsumableReadableStream);
__publicField(Consumable, "WrapByteReadableStream", ConsumableWrapByteReadableStream);

// node_modules/@yume-chan/stream-extra/esm/maybe-consumable/index.js
var maybe_consumable_exports = {};
__export(maybe_consumable_exports, {
  WrapWritableStream: () => MaybeConsumableWrapWritableStream,
  WritableStream: () => MaybeConsumableWritableStream,
  getValue: () => getValue,
  tryConsume: () => tryConsume
});

// node_modules/@yume-chan/stream-extra/esm/maybe-consumable/utils.js
function getValue(value) {
  return value instanceof Consumable ? value.value : value;
}
function tryConsume(value, callback) {
  if (value instanceof Consumable) {
    return value.tryConsume(callback);
  } else {
    return callback(value);
  }
}

// node_modules/@yume-chan/stream-extra/esm/maybe-consumable/wrap-writable.js
var MaybeConsumableWrapWritableStream = class extends WritableStream {
  constructor(stream) {
    const writer = stream.getWriter();
    super({
      write(chunk) {
        return tryConsume(chunk, (chunk2) => writer.write(chunk2));
      },
      abort(reason) {
        return writer.abort(reason);
      },
      close() {
        return writer.close();
      }
    });
  }
};

// node_modules/@yume-chan/stream-extra/esm/maybe-consumable/writable.js
var MaybeConsumableWritableStream = class extends WritableStream {
  constructor(sink, strategy) {
    let wrappedStrategy;
    if (strategy) {
      wrappedStrategy = {};
      if ("highWaterMark" in strategy) {
        wrappedStrategy.highWaterMark = strategy.highWaterMark;
      }
      if ("size" in strategy) {
        wrappedStrategy.size = (chunk) => {
          return strategy.size(chunk instanceof Consumable ? chunk.value : chunk);
        };
      }
    }
    super({
      start(controller) {
        return sink.start?.(controller);
      },
      write(chunk, controller) {
        return tryConsume(chunk, (chunk2) => sink.write?.(chunk2, controller));
      },
      abort(reason) {
        return sink.abort?.(reason);
      },
      close() {
        return sink.close?.();
      }
    }, wrappedStrategy);
  }
};

// node_modules/@yume-chan/stream-extra/esm/distribution.js
var _capacity, _buffer, _offset, _available;
var BufferCombiner = class {
  constructor(size) {
    __privateAdd(this, _capacity);
    __privateAdd(this, _buffer);
    __privateAdd(this, _offset);
    __privateAdd(this, _available);
    __privateSet(this, _capacity, size);
    __privateSet(this, _buffer, new Uint8Array(size));
    __privateSet(this, _offset, 0);
    __privateSet(this, _available, size);
  }
  /**
   * Pushes data to the combiner.
   * @param data The input data to be split or combined.
   * @returns
   * A generator that yields buffers of specified size.
   * It may yield the same buffer multiple times, consume the data before calling `next`.
   */
  *push(data) {
    let offset = 0;
    let available = data.length;
    if (__privateGet(this, _offset) !== 0) {
      if (available >= __privateGet(this, _available)) {
        __privateGet(this, _buffer).set(data.subarray(0, __privateGet(this, _available)), __privateGet(this, _offset));
        offset += __privateGet(this, _available);
        available -= __privateGet(this, _available);
        yield __privateGet(this, _buffer);
        __privateSet(this, _offset, 0);
        __privateSet(this, _available, __privateGet(this, _capacity));
        if (available === 0) {
          return;
        }
      } else {
        __privateGet(this, _buffer).set(data, __privateGet(this, _offset));
        __privateSet(this, _offset, __privateGet(this, _offset) + available);
        __privateSet(this, _available, __privateGet(this, _available) - available);
        return;
      }
    }
    while (available >= __privateGet(this, _capacity)) {
      const end = offset + __privateGet(this, _capacity);
      yield data.subarray(offset, end);
      offset = end;
      available -= __privateGet(this, _capacity);
    }
    if (available > 0) {
      __privateGet(this, _buffer).set(data.subarray(offset), __privateGet(this, _offset));
      __privateSet(this, _offset, __privateGet(this, _offset) + available);
      __privateSet(this, _available, __privateGet(this, _available) - available);
    }
  }
  flush() {
    if (__privateGet(this, _offset) === 0) {
      return void 0;
    }
    const output = __privateGet(this, _buffer).subarray(0, __privateGet(this, _offset));
    __privateSet(this, _offset, 0);
    __privateSet(this, _available, __privateGet(this, _capacity));
    return output;
  }
};
_capacity = new WeakMap();
_buffer = new WeakMap();
_offset = new WeakMap();
_available = new WeakMap();
var DistributionStream = class extends TransformStream {
  constructor(size, combine = false) {
    const combiner = combine ? new BufferCombiner(size) : void 0;
    super({
      async transform(chunk, controller) {
        await maybe_consumable_exports.tryConsume(chunk, async (chunk2) => {
          if (combiner) {
            for (const buffer2 of combiner.push(chunk2)) {
              await Consumable.ReadableStream.enqueue(controller, buffer2);
            }
          } else {
            let offset = 0;
            let available = chunk2.length;
            while (available > 0) {
              const end = offset + size;
              await Consumable.ReadableStream.enqueue(controller, chunk2.subarray(offset, end));
              offset = end;
              available -= size;
            }
          }
        });
      },
      flush(controller) {
        if (combiner) {
          const data = combiner.flush();
          if (data) {
            controller.enqueue(data);
          }
        }
      }
    });
  }
};

// node_modules/@yume-chan/stream-extra/esm/encoding.js
var Global = globalThis;
var TextDecoderStream = Global.TextDecoderStream;
var TextEncoderStream = Global.TextEncoderStream;

// node_modules/@yume-chan/stream-extra/esm/struct-deserialize.js
var StructDeserializeStream = class extends BufferedTransformStream {
  constructor(struct2) {
    super((stream) => {
      return struct2.deserialize(stream);
    });
  }
};

// node_modules/@yume-chan/event/esm/disposable.js
var _disposables;
var AutoDisposable = class {
  constructor() {
    __privateAdd(this, _disposables, []);
    this.dispose = this.dispose.bind(this);
  }
  addDisposable(disposable) {
    __privateGet(this, _disposables).push(disposable);
    return disposable;
  }
  dispose() {
    for (const disposable of __privateGet(this, _disposables)) {
      disposable.dispose();
    }
    __privateSet(this, _disposables, []);
  }
};
_disposables = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/base.js
var _adb;
var AdbServiceBase = class extends AutoDisposable {
  constructor(adb) {
    super();
    __privateAdd(this, _adb);
    __privateSet(this, _adb, adb);
  }
  get adb() {
    return __privateGet(this, _adb);
  }
};
_adb = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/framebuffer.js
var Version = struct({ version: u32 }, { littleEndian: true });
var AdbFrameBufferV1 = struct({
  bpp: u32,
  size: u32,
  width: u32,
  height: u32,
  red_offset: u32,
  red_length: u32,
  blue_offset: u32,
  blue_length: u32,
  green_offset: u32,
  green_length: u32,
  alpha_offset: u32,
  alpha_length: u32,
  data: buffer("size")
}, { littleEndian: true });
var AdbFrameBufferV2 = struct({
  bpp: u32,
  colorSpace: u32,
  size: u32,
  width: u32,
  height: u32,
  red_offset: u32,
  red_length: u32,
  blue_offset: u32,
  blue_length: u32,
  green_offset: u32,
  green_length: u32,
  alpha_offset: u32,
  alpha_length: u32,
  data: buffer("size")
}, { littleEndian: true });
var AdbFrameBufferError = class extends Error {
  constructor(message, options) {
    super(message, options);
  }
};
var AdbFrameBufferUnsupportedVersionError = class extends AdbFrameBufferError {
  constructor(version) {
    super(`Unsupported FrameBuffer version ${version}`);
  }
};
var AdbFrameBufferForbiddenError = class extends AdbFrameBufferError {
  constructor() {
    super("FrameBuffer is disabled by current app");
  }
};
async function framebuffer(adb) {
  const socket = await adb.createSocket("framebuffer:");
  const stream = new BufferedReadableStream(socket.readable);
  let version;
  try {
    ({ version } = await Version.deserialize(stream));
  } catch (e2) {
    if (e2 instanceof StructEmptyError) {
      throw new AdbFrameBufferForbiddenError();
    }
    throw e2;
  }
  switch (version) {
    case 1:
      return await AdbFrameBufferV1.deserialize(stream);
    case 2:
      return await AdbFrameBufferV2.deserialize(stream);
    default:
      throw new AdbFrameBufferUnsupportedVersionError(version);
  }
}

// node_modules/@yume-chan/adb/esm/commands/power.js
var AdbPower = class extends AdbServiceBase {
  reboot(mode = "") {
    return this.adb.createSocketAndWait(`reboot:${mode}`);
  }
  bootloader() {
    return this.reboot("bootloader");
  }
  fastboot() {
    return this.reboot("fastboot");
  }
  recovery() {
    return this.reboot("recovery");
  }
  sideload() {
    return this.reboot("sideload");
  }
  /**
   * Reboot to Qualcomm Emergency Download (EDL) Mode.
   *
   * Only works on some Qualcomm devices.
   */
  qualcommEdlMode() {
    return this.reboot("edl");
  }
  powerOff() {
    return this.adb.subprocess.noneProtocol.spawnWaitText(["reboot", "-p"]);
  }
  powerButton(longPress = false) {
    const args = ["input", "keyevent"];
    if (longPress) {
      args.push("--longpress");
    }
    args.push("POWER");
    return this.adb.subprocess.noneProtocol.spawnWaitText(args);
  }
  /**
   * Reboot to Samsung Odin download mode.
   *
   * Only works on Samsung devices.
   */
  samsungOdin() {
    return this.reboot("download");
  }
};

// node_modules/@yume-chan/adb/esm/utils/auto-reset-event.js
var _set, _queue;
var AutoResetEvent = class {
  constructor(initialSet = false) {
    __privateAdd(this, _set);
    __privateAdd(this, _queue, []);
    __privateSet(this, _set, initialSet);
  }
  wait() {
    if (!__privateGet(this, _set)) {
      __privateSet(this, _set, true);
      if (__privateGet(this, _queue).length === 0) {
        return Promise.resolve();
      }
    }
    const resolver = new PromiseResolver();
    __privateGet(this, _queue).push(resolver);
    return resolver.promise;
  }
  notifyOne() {
    if (__privateGet(this, _queue).length !== 0) {
      __privateGet(this, _queue).pop().resolve();
    } else {
      __privateSet(this, _set, false);
    }
  }
  dispose() {
    for (const item of __privateGet(this, _queue)) {
      item.reject(new Error("The AutoResetEvent has been disposed"));
    }
    __privateGet(this, _queue).length = 0;
  }
};
_set = new WeakMap();
_queue = new WeakMap();

// node_modules/@yume-chan/adb/esm/utils/base64.js
var [charToIndex, indexToChar, paddingChar] = /* @__PURE__ */ (() => {
  const charToIndex3 = [];
  const indexToChar3 = [];
  const paddingChar3 = "=".charCodeAt(0);
  function addRange2(start, end) {
    const charCodeStart = start.charCodeAt(0);
    const charCodeEnd = end.charCodeAt(0);
    for (let charCode = charCodeStart; charCode <= charCodeEnd; charCode += 1) {
      charToIndex3[charCode] = indexToChar3.length;
      indexToChar3.push(charCode);
    }
  }
  addRange2("A", "Z");
  addRange2("a", "z");
  addRange2("0", "9");
  addRange2("+", "+");
  addRange2("/", "/");
  return [charToIndex3, indexToChar3, paddingChar3];
})();
function calculateBase64EncodedLength(inputLength) {
  const remainder = inputLength % 3;
  const paddingLength = remainder !== 0 ? 3 - remainder : 0;
  return [(inputLength + paddingLength) / 3 * 4, paddingLength];
}
function encodeBase64(input, output) {
  const [outputLength, paddingLength] = calculateBase64EncodedLength(input.length);
  if (!output) {
    output = new Uint8Array(outputLength);
    encodeForward(input, output, paddingLength);
    return output;
  } else {
    if (output.length < outputLength) {
      throw new TypeError("output buffer is too small");
    }
    output = output.subarray(0, outputLength);
    if (input.buffer !== output.buffer) {
      encodeForward(input, output, paddingLength);
    } else if (output.byteOffset + output.length - (paddingLength + 1) <= input.byteOffset + input.length) {
      encodeForward(input, output, paddingLength);
    } else if (output.byteOffset >= input.byteOffset - 1) {
      encodeBackward(input, output, paddingLength);
    } else {
      throw new TypeError("input and output cannot overlap");
    }
    return outputLength;
  }
}
function encodeForward(input, output, paddingLength) {
  let inputIndex = 0;
  let outputIndex = 0;
  while (inputIndex < input.length - 2) {
    const x2 = input[inputIndex];
    inputIndex += 1;
    const y2 = input[inputIndex];
    inputIndex += 1;
    const z2 = input[inputIndex];
    inputIndex += 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex += 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4 | y2 >> 4];
    outputIndex += 1;
    output[outputIndex] = indexToChar[(y2 & 15) << 2 | z2 >> 6];
    outputIndex += 1;
    output[outputIndex] = indexToChar[z2 & 63];
    outputIndex += 1;
  }
  if (paddingLength === 2) {
    const x2 = input[inputIndex];
    inputIndex += 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex += 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4];
    outputIndex += 1;
    output[outputIndex] = paddingChar;
    outputIndex += 1;
    output[outputIndex] = paddingChar;
  } else if (paddingLength === 1) {
    const x2 = input[inputIndex];
    inputIndex += 1;
    const y2 = input[inputIndex];
    inputIndex += 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex += 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4 | y2 >> 4];
    outputIndex += 1;
    output[outputIndex] = indexToChar[(y2 & 15) << 2];
    outputIndex += 1;
    output[outputIndex] = paddingChar;
  }
}
function encodeBackward(input, output, paddingLength) {
  let inputIndex = input.length - 1;
  let outputIndex = output.length - 1;
  if (paddingLength === 2) {
    const x2 = input[inputIndex];
    inputIndex -= 1;
    output[outputIndex] = paddingChar;
    outputIndex -= 1;
    output[outputIndex] = paddingChar;
    outputIndex -= 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex -= 1;
  } else if (paddingLength === 1) {
    const y2 = input[inputIndex];
    inputIndex -= 1;
    const x2 = input[inputIndex];
    inputIndex -= 1;
    output[outputIndex] = paddingChar;
    outputIndex -= 1;
    output[outputIndex] = indexToChar[(y2 & 15) << 2];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4 | y2 >> 4];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex -= 1;
  }
  while (inputIndex >= 0) {
    const z2 = input[inputIndex];
    inputIndex -= 1;
    const y2 = input[inputIndex];
    inputIndex -= 1;
    const x2 = input[inputIndex];
    inputIndex -= 1;
    output[outputIndex] = indexToChar[z2 & 63];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[(y2 & 15) << 2 | z2 >> 6];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[(x2 & 3) << 4 | y2 >> 4];
    outputIndex -= 1;
    output[outputIndex] = indexToChar[x2 >> 2];
    outputIndex -= 1;
  }
}

// node_modules/@yume-chan/adb/esm/utils/hex.js
function hexCharToNumber(char) {
  if (char < 48) {
    throw new TypeError(`Invalid hex char ${char}`);
  }
  if (char < 58) {
    return char - 48;
  }
  if (char < 65) {
    throw new TypeError(`Invalid hex char ${char}`);
  }
  if (char < 71) {
    return char - 55;
  }
  if (char < 97) {
    throw new TypeError(`Invalid hex char ${char}`);
  }
  if (char < 103) {
    return char - 87;
  }
  throw new TypeError(`Invalid hex char ${char}`);
}
function hexToNumber(data) {
  let result = 0;
  for (let i2 = 0; i2 < data.length; i2 += 1) {
    result = result << 4 | hexCharToNumber(data[i2]);
  }
  return result;
}

// node_modules/@yume-chan/adb/esm/utils/no-op.js
var NOOP = /* @__NO_SIDE_EFFECTS__ */ () => {
};
function unreachable(...args) {
  throw new Error("Unreachable. Arguments:\n" + args.join("\n"));
}

// node_modules/@yume-chan/adb/esm/utils/sequence-equal.js
function sequenceEqual(a2, b2) {
  if (a2.length !== b2.length) {
    return false;
  }
  for (let i2 = 0; i2 < a2.length; i2 += 1) {
    if (a2[i2] !== b2[i2]) {
      return false;
    }
  }
  return true;
}

// node_modules/@yume-chan/adb/esm/commands/reverse.js
var AdbReverseStringResponse = struct({
  length: string(4),
  content: string({
    field: "length",
    convert(value) {
      return Number.parseInt(value, 16);
    },
    back(value) {
      return value.toString(16).padStart(4, "0");
    }
  })
}, { littleEndian: true });
var AdbReverseError = class extends Error {
  constructor(message) {
    super(message);
  }
};
var AdbReverseNotSupportedError = class extends AdbReverseError {
  constructor() {
    super("ADB reverse tunnel is not supported on this device when connected wirelessly.");
  }
};
var AdbReverseErrorResponse = extend(AdbReverseStringResponse, {}, {
  postDeserialize(value) {
    if (value.content === "more than one device/emulator") {
      throw new AdbReverseNotSupportedError();
    } else {
      throw new AdbReverseError(value.content);
    }
  }
});
function decimalToNumber(buffer2) {
  let value = 0;
  for (const byte of buffer2) {
    if (byte < 48 || byte > 57) {
      return value;
    }
    value = value * 10 + byte - 48;
  }
  return value;
}
var OKAY = encodeUtf8("OKAY");
var _deviceAddressToLocalAddress;
var AdbReverseService = class extends AdbServiceBase {
  constructor() {
    super(...arguments);
    __privateAdd(this, _deviceAddressToLocalAddress, /* @__PURE__ */ new Map());
  }
  async createBufferedStream(service) {
    const socket = await this.adb.createSocket(service);
    return new BufferedReadableStream(socket.readable);
  }
  async sendRequest(service) {
    const stream = await this.createBufferedStream(service);
    const response = await stream.readExactly(4);
    if (!sequenceEqual(response, OKAY)) {
      await AdbReverseErrorResponse.deserialize(stream);
    }
    return stream;
  }
  /**
   * Get a list of all reverse port forwarding on the device.
   */
  async list() {
    const stream = await this.createBufferedStream("reverse:list-forward");
    const response = await AdbReverseStringResponse.deserialize(stream);
    return response.content.split("\n").filter((line) => !!line).map((line) => {
      const [deviceSerial, localName, remoteName] = line.split(" ");
      return { deviceSerial, localName, remoteName };
    });
  }
  /**
   * Add a reverse port forwarding for a program that already listens on a port.
   */
  async addExternal(deviceAddress, localAddress) {
    const stream = await this.sendRequest(`reverse:forward:${deviceAddress};${localAddress}`);
    if (deviceAddress.startsWith("tcp:")) {
      const position = stream.position;
      try {
        const length = hexToNumber(await stream.readExactly(4));
        const port = decimalToNumber(await stream.readExactly(length));
        deviceAddress = `tcp:${port}`;
      } catch (e2) {
        if (e2 instanceof ExactReadableEndedError && stream.position === position) {
        } else {
          throw e2;
        }
      }
    }
    return deviceAddress;
  }
  /**
   * Add a reverse port forwarding.
   */
  async add(deviceAddress, handler, localAddress) {
    localAddress = await this.adb.transport.addReverseTunnel(handler, localAddress);
    try {
      deviceAddress = await this.addExternal(deviceAddress, localAddress);
      __privateGet(this, _deviceAddressToLocalAddress).set(deviceAddress, localAddress);
      return deviceAddress;
    } catch (e2) {
      await this.adb.transport.removeReverseTunnel(localAddress);
      throw e2;
    }
  }
  /**
   * Remove a reverse port forwarding.
   */
  async remove(deviceAddress) {
    const localAddress = __privateGet(this, _deviceAddressToLocalAddress).get(deviceAddress);
    if (localAddress) {
      await this.adb.transport.removeReverseTunnel(localAddress);
    }
    await this.sendRequest(`reverse:killforward:${deviceAddress}`);
  }
  /**
   * Remove all reverse port forwarding, including the ones added by other programs.
   */
  async removeAll() {
    await this.adb.transport.clearReverseTunnels();
    __privateGet(this, _deviceAddressToLocalAddress).clear();
    await this.sendRequest(`reverse:killforward-all`);
  }
};
_deviceAddressToLocalAddress = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/none/process.js
var _socket, _exited;
var AdbNoneProtocolProcessImpl = class {
  constructor(socket, signal) {
    __privateAdd(this, _socket);
    __privateAdd(this, _exited);
    __privateSet(this, _socket, socket);
    if (signal) {
      const exited = new PromiseResolver();
      __privateGet(this, _socket).closed.then(() => exited.resolve(void 0), (e2) => exited.reject(e2));
      signal.addEventListener("abort", () => {
        exited.reject(signal.reason);
        __privateGet(this, _socket).close();
      });
      __privateSet(this, _exited, exited.promise);
    } else {
      __privateSet(this, _exited, __privateGet(this, _socket).closed);
    }
  }
  get stdin() {
    return __privateGet(this, _socket).writable;
  }
  get output() {
    return __privateGet(this, _socket).readable;
  }
  get exited() {
    return __privateGet(this, _exited);
  }
  kill() {
    return __privateGet(this, _socket).close();
  }
};
_socket = new WeakMap();
_exited = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/none/pty.js
var _socket2, _writer, _input;
var AdbNoneProtocolPtyProcess = class {
  constructor(socket) {
    __privateAdd(this, _socket2);
    __privateAdd(this, _writer);
    __privateAdd(this, _input);
    __privateSet(this, _socket2, socket);
    __privateSet(this, _writer, __privateGet(this, _socket2).writable.getWriter());
    __privateSet(this, _input, new maybe_consumable_exports.WritableStream({
      write: (chunk) => __privateGet(this, _writer).write(chunk)
    }));
  }
  get input() {
    return __privateGet(this, _input);
  }
  get output() {
    return __privateGet(this, _socket2).readable;
  }
  get exited() {
    return __privateGet(this, _socket2).closed;
  }
  sigint() {
    return __privateGet(this, _writer).write(new Uint8Array([3]));
  }
  kill() {
    return __privateGet(this, _socket2).close();
  }
};
_socket2 = new WeakMap();
_writer = new WeakMap();
_input = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/utils.js
function escapeArg(s2) {
  let result = "";
  result += `'`;
  let base = 0;
  while (true) {
    const found = s2.indexOf(`'`, base);
    if (found === -1) {
      result += s2.substring(base);
      break;
    }
    result += s2.substring(base, found);
    result += String.raw`'\''`;
    base = found + 1;
  }
  result += `'`;
  return result;
}
function splitCommand(command) {
  const result = [];
  let quote;
  let isEscaped = false;
  let start = 0;
  for (let i2 = 0, len = command.length; i2 < len; i2 += 1) {
    if (isEscaped) {
      isEscaped = false;
      continue;
    }
    const char = command.charAt(i2);
    switch (char) {
      case " ":
        if (!quote && i2 !== start) {
          result.push(command.substring(start, i2));
          start = i2 + 1;
        }
        break;
      case "'":
      case '"':
        if (!quote) {
          quote = char;
        } else if (char === quote) {
          quote = void 0;
        }
        break;
      case "\\":
        isEscaped = true;
        break;
    }
  }
  if (start < command.length) {
    result.push(command.substring(start));
  }
  return result;
}

// node_modules/@yume-chan/adb/esm/commands/subprocess/none/spawner.js
var _spawn;
var AdbNoneProtocolSpawner = class {
  constructor(spawn) {
    __privateAdd(this, _spawn);
    __privateSet(this, _spawn, spawn);
  }
  spawn(command, signal) {
    signal?.throwIfAborted();
    if (typeof command === "string") {
      command = splitCommand(command);
    }
    return __privateGet(this, _spawn).call(this, command, signal);
  }
  async spawnWait(command) {
    const process = await this.spawn(command);
    return await process.output.pipeThrough(new ConcatBufferStream());
  }
  async spawnWaitText(command) {
    const process = await this.spawn(command);
    return await process.output.pipeThrough(new TextDecoderStream()).pipeThrough(new ConcatStringStream());
  }
};
_spawn = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/none/service.js
var _adb2;
var AdbNoneProtocolSubprocessService = class extends AdbNoneProtocolSpawner {
  constructor(adb) {
    super(async (command, signal) => {
      const socket = await __privateGet(this, _adb2).createSocket(`exec:${command.join(" ")}`);
      if (signal?.aborted) {
        await socket.close();
        throw signal.reason;
      }
      return new AdbNoneProtocolProcessImpl(socket, signal);
    });
    __privateAdd(this, _adb2);
    __privateSet(this, _adb2, adb);
  }
  get adb() {
    return __privateGet(this, _adb2);
  }
  async pty(command) {
    if (command === void 0) {
      command = "";
    } else if (Array.isArray(command)) {
      command = command.join(" ");
    }
    return new AdbNoneProtocolPtyProcess(
      // https://github.com/microsoft/typescript/issues/17002
      await __privateGet(this, _adb2).createSocket(`shell:${command}`)
    );
  }
};
_adb2 = new WeakMap();

// node_modules/@yume-chan/adb/esm/features.js
var AdbFeature = {
  ShellV2: "shell_v2",
  Cmd: "cmd",
  StatV2: "stat_v2",
  ListV2: "ls_v2",
  FixedPushMkdir: "fixed_push_mkdir",
  Abb: "abb",
  AbbExec: "abb_exec",
  SendReceiveV2: "sendrecv_v2",
  DelayedAck: "delayed_ack"
};

// node_modules/@yume-chan/adb/esm/commands/subprocess/shell/shared.js
var AdbShellProtocolId = {
  Stdin: 0,
  Stdout: 1,
  Stderr: 2,
  Exit: 3,
  CloseStdin: 4,
  WindowSizeChange: 5
};
var AdbShellProtocolPacket = struct({
  id: u8(),
  data: buffer(u32)
}, { littleEndian: true });

// node_modules/@yume-chan/adb/esm/commands/subprocess/shell/process.js
var _socket3, _writer2, _stdin, _stdout, _stderr, _exited2;
var AdbShellProtocolProcessImpl = class {
  constructor(socket, signal) {
    __privateAdd(this, _socket3);
    __privateAdd(this, _writer2);
    __privateAdd(this, _stdin);
    __privateAdd(this, _stdout);
    __privateAdd(this, _stderr);
    __privateAdd(this, _exited2);
    __privateSet(this, _socket3, socket);
    let stdoutController;
    let stderrController;
    __privateSet(this, _stdout, new PushReadableStream((controller) => {
      stdoutController = controller;
    }));
    __privateSet(this, _stderr, new PushReadableStream((controller) => {
      stderrController = controller;
    }));
    const exited = new PromiseResolver();
    __privateSet(this, _exited2, exited.promise);
    socket.readable.pipeThrough(new StructDeserializeStream(AdbShellProtocolPacket)).pipeTo(new WritableStream({
      write: async (chunk) => {
        switch (chunk.id) {
          case AdbShellProtocolId.Exit:
            exited.resolve(chunk.data[0]);
            break;
          case AdbShellProtocolId.Stdout:
            await stdoutController.enqueue(chunk.data);
            break;
          case AdbShellProtocolId.Stderr:
            await stderrController.enqueue(chunk.data);
            break;
          default:
            break;
        }
      }
    })).then(() => {
      stdoutController.close();
      stderrController.close();
      exited.reject(new Error("Socket ended without exit message"));
    }, (e2) => {
      stdoutController.error(e2);
      stderrController.error(e2);
      exited.reject(e2);
    });
    if (signal) {
      signal.addEventListener("abort", () => {
        exited.reject(signal.reason);
        __privateGet(this, _socket3).close();
      });
    }
    __privateSet(this, _writer2, __privateGet(this, _socket3).writable.getWriter());
    __privateSet(this, _stdin, new maybe_consumable_exports.WritableStream({
      write: async (chunk) => {
        await __privateGet(this, _writer2).write(AdbShellProtocolPacket.serialize({
          id: AdbShellProtocolId.Stdin,
          data: chunk
        }));
      },
      close: () => (
        // Only shell protocol + raw mode supports closing stdin
        __privateGet(this, _writer2).write(AdbShellProtocolPacket.serialize({
          id: AdbShellProtocolId.CloseStdin,
          data: EmptyUint8Array
        }))
      )
    }));
  }
  get stdin() {
    return __privateGet(this, _stdin);
  }
  get stdout() {
    return __privateGet(this, _stdout);
  }
  get stderr() {
    return __privateGet(this, _stderr);
  }
  get exited() {
    return __privateGet(this, _exited2);
  }
  kill() {
    return __privateGet(this, _socket3).close();
  }
};
_socket3 = new WeakMap();
_writer2 = new WeakMap();
_stdin = new WeakMap();
_stdout = new WeakMap();
_stderr = new WeakMap();
_exited2 = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/shell/pty.js
var _socket4, _writer3, _input2, _stdout2, _exited3, _AdbShellProtocolPtyProcess_instances, writeStdin_fn;
var AdbShellProtocolPtyProcess = class {
  constructor(socket) {
    __privateAdd(this, _AdbShellProtocolPtyProcess_instances);
    __privateAdd(this, _socket4);
    __privateAdd(this, _writer3);
    __privateAdd(this, _input2);
    __privateAdd(this, _stdout2);
    __privateAdd(this, _exited3, new PromiseResolver());
    __privateSet(this, _socket4, socket);
    let stdoutController;
    __privateSet(this, _stdout2, new PushReadableStream((controller) => {
      stdoutController = controller;
    }));
    socket.readable.pipeThrough(new StructDeserializeStream(AdbShellProtocolPacket)).pipeTo(new WritableStream({
      write: async (chunk) => {
        switch (chunk.id) {
          case AdbShellProtocolId.Exit:
            __privateGet(this, _exited3).resolve(chunk.data[0]);
            break;
          case AdbShellProtocolId.Stdout:
            await stdoutController.enqueue(chunk.data);
            break;
        }
      }
    })).then(() => {
      stdoutController.close();
      __privateGet(this, _exited3).reject(new Error("Socket ended without exit message"));
    }, (e2) => {
      stdoutController.error(e2);
      __privateGet(this, _exited3).reject(e2);
    });
    __privateSet(this, _writer3, __privateGet(this, _socket4).writable.getWriter());
    __privateSet(this, _input2, new maybe_consumable_exports.WritableStream({
      write: (chunk) => __privateMethod(this, _AdbShellProtocolPtyProcess_instances, writeStdin_fn).call(this, chunk)
    }));
  }
  get input() {
    return __privateGet(this, _input2);
  }
  get output() {
    return __privateGet(this, _stdout2);
  }
  get exited() {
    return __privateGet(this, _exited3).promise;
  }
  async resize(rows, cols) {
    await __privateGet(this, _writer3).write(AdbShellProtocolPacket.serialize({
      id: AdbShellProtocolId.WindowSizeChange,
      // The "correct" format is `${rows}x${cols},${x_pixels}x${y_pixels}`
      // However, according to https://linux.die.net/man/4/tty_ioctl
      // `x_pixels` and `y_pixels` are unused, so always sending `0` should be fine.
      data: encodeUtf8(`${rows}x${cols},0x0\0`)
    }));
  }
  sigint() {
    return __privateMethod(this, _AdbShellProtocolPtyProcess_instances, writeStdin_fn).call(this, new Uint8Array([3]));
  }
  kill() {
    return __privateGet(this, _socket4).close();
  }
};
_socket4 = new WeakMap();
_writer3 = new WeakMap();
_input2 = new WeakMap();
_stdout2 = new WeakMap();
_exited3 = new WeakMap();
_AdbShellProtocolPtyProcess_instances = new WeakSet();
writeStdin_fn = function(chunk) {
  return __privateGet(this, _writer3).write(AdbShellProtocolPacket.serialize({
    id: AdbShellProtocolId.Stdin,
    data: chunk
  }));
};

// node_modules/@yume-chan/adb/esm/commands/subprocess/shell/spawner.js
var _spawn2;
var AdbShellProtocolSpawner = class {
  constructor(spawn) {
    __privateAdd(this, _spawn2);
    __privateSet(this, _spawn2, spawn);
  }
  spawn(command, signal) {
    signal?.throwIfAborted();
    if (typeof command === "string") {
      command = splitCommand(command);
    }
    return __privateGet(this, _spawn2).call(this, command, signal);
  }
  async spawnWait(command) {
    const process = await this.spawn(command);
    const [stdout, stderr, exitCode] = await Promise.all([
      process.stdout.pipeThrough(new ConcatBufferStream()),
      process.stderr.pipeThrough(new ConcatBufferStream()),
      process.exited
    ]);
    return { stdout, stderr, exitCode };
  }
  async spawnWaitText(command) {
    const process = await this.spawn(command);
    const [stdout, stderr, exitCode] = await Promise.all([
      process.stdout.pipeThrough(new TextDecoderStream()).pipeThrough(new ConcatStringStream()),
      process.stderr.pipeThrough(new TextDecoderStream()).pipeThrough(new ConcatStringStream()),
      process.exited
    ]);
    return { stdout, stderr, exitCode };
  }
};
_spawn2 = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/shell/service.js
var _adb3;
var AdbShellProtocolSubprocessService = class extends AdbShellProtocolSpawner {
  constructor(adb) {
    super(async (command, signal) => {
      const socket = await __privateGet(this, _adb3).createSocket(`shell,v2,raw:${command.join(" ")}`);
      if (signal?.aborted) {
        await socket.close();
        throw signal.reason;
      }
      return new AdbShellProtocolProcessImpl(socket, signal);
    });
    __privateAdd(this, _adb3);
    __privateSet(this, _adb3, adb);
  }
  get adb() {
    return __privateGet(this, _adb3);
  }
  get isSupported() {
    return __privateGet(this, _adb3).canUseFeature(AdbFeature.ShellV2);
  }
  async pty(options) {
    let service = "shell,v2,pty";
    if (options?.terminalType) {
      service += `,TERM=` + options.terminalType;
    }
    service += ":";
    if (options) {
      if (typeof options.command === "string") {
        service += options.command;
      } else if (Array.isArray(options.command)) {
        service += options.command.join(" ");
      }
    }
    return new AdbShellProtocolPtyProcess(await __privateGet(this, _adb3).createSocket(service));
  }
};
_adb3 = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/subprocess/service.js
var _adb4, _noneProtocol, _shellProtocol;
var AdbSubprocessService = class {
  constructor(adb) {
    __privateAdd(this, _adb4);
    __privateAdd(this, _noneProtocol);
    __privateAdd(this, _shellProtocol);
    __privateSet(this, _adb4, adb);
    __privateSet(this, _noneProtocol, new AdbNoneProtocolSubprocessService(adb));
    if (adb.canUseFeature(AdbFeature.ShellV2)) {
      __privateSet(this, _shellProtocol, new AdbShellProtocolSubprocessService(adb));
    }
  }
  get adb() {
    return __privateGet(this, _adb4);
  }
  get noneProtocol() {
    return __privateGet(this, _noneProtocol);
  }
  get shellProtocol() {
    return __privateGet(this, _shellProtocol);
  }
};
_adb4 = new WeakMap();
_noneProtocol = new WeakMap();
_shellProtocol = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/sync/response.js
function encodeAsciiUnchecked(value) {
  const result = new Uint8Array(value.length);
  for (let i2 = 0; i2 < value.length; i2 += 1) {
    result[i2] = value.charCodeAt(i2);
  }
  return result;
}
// @__NO_SIDE_EFFECTS__
function adbSyncEncodeId(value) {
  const buffer2 = encodeAsciiUnchecked(value);
  return getUint32LittleEndian(buffer2, 0);
}
var AdbSyncResponseId = {
  Entry: /* @__PURE__ */ adbSyncEncodeId("DENT"),
  Entry2: /* @__PURE__ */ adbSyncEncodeId("DNT2"),
  Lstat: /* @__PURE__ */ adbSyncEncodeId("STAT"),
  Stat: /* @__PURE__ */ adbSyncEncodeId("STA2"),
  Lstat2: /* @__PURE__ */ adbSyncEncodeId("LST2"),
  Done: /* @__PURE__ */ adbSyncEncodeId("DONE"),
  Data: /* @__PURE__ */ adbSyncEncodeId("DATA"),
  Ok: /* @__PURE__ */ adbSyncEncodeId("OKAY"),
  Fail: /* @__PURE__ */ adbSyncEncodeId("FAIL")
};
var AdbSyncError = class extends Error {
};
var AdbSyncFailResponse = struct({ message: string(u32) }, {
  littleEndian: true,
  postDeserialize(value) {
    throw new AdbSyncError(value.message);
  }
});
async function adbSyncReadResponse(stream, id, type) {
  if (typeof id === "string") {
    id = /* @__PURE__ */ adbSyncEncodeId(id);
  }
  const buffer2 = await stream.readExactly(4);
  switch (getUint32LittleEndian(buffer2, 0)) {
    case AdbSyncResponseId.Fail:
      await AdbSyncFailResponse.deserialize(stream);
      throw new Error("Unreachable");
    case id:
      return await type.deserialize(stream);
    default:
      throw new Error(`Expected '${id}', but got '${decodeUtf8(buffer2)}'`);
  }
}
async function* adbSyncReadResponses(stream, id, type) {
  if (typeof id === "string") {
    id = /* @__PURE__ */ adbSyncEncodeId(id);
  }
  while (true) {
    const buffer2 = await stream.readExactly(4);
    switch (getUint32LittleEndian(buffer2, 0)) {
      case AdbSyncResponseId.Fail:
        await AdbSyncFailResponse.deserialize(stream);
        unreachable();
      case AdbSyncResponseId.Done:
        await stream.readExactly(type.size);
        return;
      case id:
        yield await type.deserialize(stream);
        break;
      default:
        throw new Error(`Expected '${id}' or '${AdbSyncResponseId.Done}', but got '${decodeUtf8(buffer2)}'`);
    }
  }
}

// node_modules/@yume-chan/adb/esm/commands/sync/request.js
var AdbSyncRequestId = {
  List: adbSyncEncodeId("LIST"),
  ListV2: adbSyncEncodeId("LIS2"),
  Send: adbSyncEncodeId("SEND"),
  SendV2: adbSyncEncodeId("SND2"),
  Lstat: adbSyncEncodeId("STAT"),
  Stat: adbSyncEncodeId("STA2"),
  LstatV2: adbSyncEncodeId("LST2"),
  Data: adbSyncEncodeId("DATA"),
  Done: adbSyncEncodeId("DONE"),
  Receive: adbSyncEncodeId("RECV")
};
var AdbSyncNumberRequest = struct({ id: u32, arg: u32 }, { littleEndian: true });
async function adbSyncWriteRequest(writable, id, value) {
  if (typeof id === "string") {
    id = adbSyncEncodeId(id);
  }
  if (typeof value === "number") {
    await writable.write(AdbSyncNumberRequest.serialize({ id, arg: value }));
    return;
  }
  if (typeof value === "string") {
    value = encodeUtf8(value);
  }
  await writable.write(AdbSyncNumberRequest.serialize({ id, arg: value.length }));
  await writable.write(value);
}

// node_modules/@yume-chan/adb/esm/commands/sync/stat.js
var LinuxFileType = {
  Directory: 4,
  File: 8,
  Link: 10
};
var AdbSyncLstatResponse = struct({ mode: u32, size: u32, mtime: u32 }, {
  littleEndian: true,
  extra: {
    get type() {
      return this.mode >> 12;
    },
    get permission() {
      return this.mode & 4095;
    }
  },
  postDeserialize(value) {
    if (value.mode === 0 && value.size === 0 && value.mtime === 0) {
      throw new Error("lstat error");
    }
    return value;
  }
});
var AdbSyncStatErrorCode = {
  SUCCESS: 0,
  EACCES: 13,
  EEXIST: 17,
  EFAULT: 14,
  EFBIG: 27,
  EINTR: 4,
  EINVAL: 22,
  EIO: 5,
  EISDIR: 21,
  ELOOP: 40,
  EMFILE: 24,
  ENAMETOOLONG: 36,
  ENFILE: 23,
  ENOENT: 2,
  ENOMEM: 12,
  ENOSPC: 28,
  ENOTDIR: 20,
  EOVERFLOW: 75,
  EPERM: 1,
  EROFS: 30,
  ETXTBSY: 26
};
var AdbSyncStatErrorName = /* @__PURE__ */ (() => Object.fromEntries(Object.entries(AdbSyncStatErrorCode).map(([key, value]) => [
  value,
  key
])))();
var AdbSyncStatResponse = struct({
  error: u32(),
  dev: u64,
  ino: u64,
  mode: u32,
  nlink: u32,
  uid: u32,
  gid: u32,
  size: u64,
  atime: u64,
  mtime: u64,
  ctime: u64
}, {
  littleEndian: true,
  extra: {
    get type() {
      return this.mode >> 12;
    },
    get permission() {
      return this.mode & 4095;
    }
  },
  postDeserialize(value) {
    if (value.error) {
      throw new Error(AdbSyncStatErrorName[value.error]);
    }
    return value;
  }
});
async function adbSyncLstat(socket, path, v2) {
  const locked = await socket.lock();
  try {
    if (v2) {
      await adbSyncWriteRequest(locked, AdbSyncRequestId.LstatV2, path);
      return await adbSyncReadResponse(locked, AdbSyncResponseId.Lstat2, AdbSyncStatResponse);
    } else {
      await adbSyncWriteRequest(locked, AdbSyncRequestId.Lstat, path);
      const response = await adbSyncReadResponse(locked, AdbSyncResponseId.Lstat, AdbSyncLstatResponse);
      return {
        mode: response.mode,
        // Convert to `BigInt` to make it compatible with `AdbSyncStatResponse`
        size: BigInt(response.size),
        mtime: BigInt(response.mtime),
        get type() {
          return response.type;
        },
        get permission() {
          return response.permission;
        }
      };
    }
  } finally {
    locked.release();
  }
}
async function adbSyncStat(socket, path) {
  const locked = await socket.lock();
  try {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.Stat, path);
    return await adbSyncReadResponse(locked, AdbSyncResponseId.Stat, AdbSyncStatResponse);
  } finally {
    locked.release();
  }
}

// node_modules/@yume-chan/adb/esm/commands/sync/list.js
var AdbSyncEntryResponse = extend(AdbSyncLstatResponse, {
  name: string(u32)
});
var AdbSyncEntry2Response = extend(AdbSyncStatResponse, {
  name: string(u32)
});
async function* adbSyncOpenDirV2(socket, path) {
  const locked = await socket.lock();
  try {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.ListV2, path);
    for await (const item of adbSyncReadResponses(locked, AdbSyncResponseId.Entry2, AdbSyncEntry2Response)) {
      if (item.error !== AdbSyncStatErrorCode.SUCCESS) {
        continue;
      }
      yield item;
    }
  } finally {
    locked.release();
  }
}
async function* adbSyncOpenDirV1(socket, path) {
  const locked = await socket.lock();
  try {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.List, path);
    for await (const item of adbSyncReadResponses(locked, AdbSyncResponseId.Entry, AdbSyncEntryResponse)) {
      yield item;
    }
  } finally {
    locked.release();
  }
}
async function* adbSyncOpenDir(socket, path, v2) {
  if (v2) {
    yield* adbSyncOpenDirV2(socket, path);
  } else {
    for await (const item of adbSyncOpenDirV1(socket, path)) {
      yield {
        mode: item.mode,
        size: BigInt(item.size),
        mtime: BigInt(item.mtime),
        get type() {
          return item.type;
        },
        get permission() {
          return item.permission;
        },
        name: item.name
      };
    }
  }
}

// node_modules/@yume-chan/adb/esm/commands/sync/pull.js
var AdbSyncDataResponse = struct({ data: buffer(u32) }, { littleEndian: true });
async function* adbSyncPullGenerator(socket, path) {
  const locked = await socket.lock();
  let done = false;
  try {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.Receive, path);
    for await (const packet of adbSyncReadResponses(locked, AdbSyncResponseId.Data, AdbSyncDataResponse)) {
      yield packet.data;
    }
    done = true;
  } catch (e2) {
    done = true;
    throw e2;
  } finally {
    if (!done) {
      for await (const packet of adbSyncReadResponses(locked, AdbSyncResponseId.Data, AdbSyncDataResponse)) {
        void packet;
      }
    }
    locked.release();
  }
}
function adbSyncPull(socket, path) {
  return ReadableStream.from(adbSyncPullGenerator(socket, path));
}

// node_modules/@yume-chan/adb/esm/commands/sync/push.js
var ADB_SYNC_MAX_PACKET_SIZE = 64 * 1024;
var AdbSyncOkResponse = struct({ unused: u32 }, { littleEndian: true });
async function pipeFileData(locked, file, packetSize, mtime) {
  const abortController = new AbortController2();
  file.pipeThrough(new DistributionStream(packetSize, true)).pipeTo(new maybe_consumable_exports.WritableStream({
    write(chunk) {
      return adbSyncWriteRequest(locked, AdbSyncRequestId.Data, chunk);
    }
  }), { signal: abortController.signal }).then(async () => {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.Done, mtime);
    await locked.flush();
  }, NOOP);
  await adbSyncReadResponse(locked, AdbSyncResponseId.Ok, AdbSyncOkResponse).catch((e2) => {
    abortController.abort();
    throw e2;
  });
}
async function adbSyncPushV1({ socket, filename, file, type = LinuxFileType.File, permission = 438, mtime = Date.now() / 1e3 | 0, packetSize = ADB_SYNC_MAX_PACKET_SIZE }) {
  const locked = await socket.lock();
  try {
    const mode = type << 12 | permission;
    const pathAndMode = `${filename},${mode.toString()}`;
    await adbSyncWriteRequest(locked, AdbSyncRequestId.Send, pathAndMode);
    await pipeFileData(locked, file, packetSize, mtime);
  } finally {
    locked.release();
  }
}
var AdbSyncSendV2Flags = {
  None: 0,
  Brotli: 1,
  /**
   * 2
   */
  Lz4: 1 << 1,
  /**
   * 4
   */
  Zstd: 1 << 2,
  DryRun: 2147483648
};
var AdbSyncSendV2Request = struct({ id: u32, mode: u32, flags: u32() }, { littleEndian: true });
async function adbSyncPushV2({ socket, filename, file, type = LinuxFileType.File, permission = 438, mtime = Date.now() / 1e3 | 0, packetSize = ADB_SYNC_MAX_PACKET_SIZE, dryRun = false }) {
  const locked = await socket.lock();
  try {
    await adbSyncWriteRequest(locked, AdbSyncRequestId.SendV2, filename);
    const mode = type << 12 | permission;
    let flags = AdbSyncSendV2Flags.None;
    if (dryRun) {
      flags |= AdbSyncSendV2Flags.DryRun;
    }
    await locked.write(AdbSyncSendV2Request.serialize({
      id: AdbSyncRequestId.SendV2,
      mode,
      flags
    }));
    await pipeFileData(locked, file, packetSize, mtime);
  } finally {
    locked.release();
  }
}
function adbSyncPush(options) {
  if (options.v2) {
    return adbSyncPushV2(options);
  }
  if (options.dryRun) {
    throw new Error("dryRun is not supported in v1");
  }
  return adbSyncPushV1(options);
}

// node_modules/@yume-chan/adb/esm/commands/sync/socket.js
var _writer4, _readable4, _socketLock, _writeLock, _combiner, _AdbSyncSocketLocked_instances, write_fn;
var AdbSyncSocketLocked = class {
  constructor(writer, readable, bufferSize, lock) {
    __privateAdd(this, _AdbSyncSocketLocked_instances);
    __privateAdd(this, _writer4);
    __privateAdd(this, _readable4);
    __privateAdd(this, _socketLock);
    __privateAdd(this, _writeLock, new AutoResetEvent());
    __privateAdd(this, _combiner);
    __privateSet(this, _writer4, writer);
    __privateSet(this, _readable4, readable);
    __privateSet(this, _socketLock, lock);
    __privateSet(this, _combiner, new BufferCombiner(bufferSize));
  }
  get position() {
    return __privateGet(this, _readable4).position;
  }
  async flush() {
    try {
      await __privateGet(this, _writeLock).wait();
      const buffer2 = __privateGet(this, _combiner).flush();
      if (buffer2) {
        await __privateMethod(this, _AdbSyncSocketLocked_instances, write_fn).call(this, buffer2);
      }
    } finally {
      __privateGet(this, _writeLock).notifyOne();
    }
  }
  async write(data) {
    try {
      await __privateGet(this, _writeLock).wait();
      for (const buffer2 of __privateGet(this, _combiner).push(data)) {
        await __privateMethod(this, _AdbSyncSocketLocked_instances, write_fn).call(this, buffer2);
      }
    } finally {
      __privateGet(this, _writeLock).notifyOne();
    }
  }
  async readExactly(length) {
    await this.flush();
    return await __privateGet(this, _readable4).readExactly(length);
  }
  release() {
    __privateGet(this, _combiner).flush();
    __privateGet(this, _socketLock).notifyOne();
  }
  async close() {
    await __privateGet(this, _readable4).cancel();
  }
};
_writer4 = new WeakMap();
_readable4 = new WeakMap();
_socketLock = new WeakMap();
_writeLock = new WeakMap();
_combiner = new WeakMap();
_AdbSyncSocketLocked_instances = new WeakSet();
write_fn = function(buffer2) {
  return Consumable.WritableStream.write(__privateGet(this, _writer4), buffer2);
};
var _lock, _socket5, _locked;
var AdbSyncSocket = class {
  constructor(socket, bufferSize) {
    __privateAdd(this, _lock, new AutoResetEvent());
    __privateAdd(this, _socket5);
    __privateAdd(this, _locked);
    __privateSet(this, _socket5, socket);
    __privateSet(this, _locked, new AdbSyncSocketLocked(socket.writable.getWriter(), new BufferedReadableStream(socket.readable), bufferSize, __privateGet(this, _lock)));
  }
  async lock() {
    await __privateGet(this, _lock).wait();
    return __privateGet(this, _locked);
  }
  async close() {
    await __privateGet(this, _locked).close();
    await __privateGet(this, _socket5).close();
  }
};
_lock = new WeakMap();
_socket5 = new WeakMap();
_locked = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/sync/sync.js
function dirname(path) {
  const end = path.lastIndexOf("/");
  if (end === -1) {
    throw new Error(`Invalid path`);
  }
  if (end === 0) {
    return "/";
  }
  return path.substring(0, end);
}
var _supportsStat, _supportsListV2, _fixedPushMkdir, _supportsSendReceiveV2, _needPushMkdirWorkaround;
var AdbSync = class {
  constructor(adb, socket) {
    __publicField(this, "_adb");
    __publicField(this, "_socket");
    __privateAdd(this, _supportsStat);
    __privateAdd(this, _supportsListV2);
    __privateAdd(this, _fixedPushMkdir);
    __privateAdd(this, _supportsSendReceiveV2);
    __privateAdd(this, _needPushMkdirWorkaround);
    this._adb = adb;
    this._socket = new AdbSyncSocket(socket, adb.maxPayloadSize);
    __privateSet(this, _supportsStat, adb.canUseFeature(AdbFeature.StatV2));
    __privateSet(this, _supportsListV2, adb.canUseFeature(AdbFeature.ListV2));
    __privateSet(this, _fixedPushMkdir, adb.canUseFeature(AdbFeature.FixedPushMkdir));
    __privateSet(this, _supportsSendReceiveV2, adb.canUseFeature(AdbFeature.SendReceiveV2));
    __privateSet(this, _needPushMkdirWorkaround, this._adb.canUseFeature(AdbFeature.ShellV2) && !this.fixedPushMkdir);
  }
  get supportsStat() {
    return __privateGet(this, _supportsStat);
  }
  get supportsListV2() {
    return __privateGet(this, _supportsListV2);
  }
  get fixedPushMkdir() {
    return __privateGet(this, _fixedPushMkdir);
  }
  get supportsSendReceiveV2() {
    return __privateGet(this, _supportsSendReceiveV2);
  }
  get needPushMkdirWorkaround() {
    return __privateGet(this, _needPushMkdirWorkaround);
  }
  /**
   * Gets information of a file or folder.
   *
   * If `path` points to a symbolic link, the returned information is about the link itself (with `type` being `LinuxFileType.Link`).
   */
  async lstat(path) {
    return await adbSyncLstat(this._socket, path, __privateGet(this, _supportsStat));
  }
  /**
   * Gets the information of a file or folder.
   *
   * If `path` points to a symbolic link, it will be resolved and the returned information is about the target (with `type` being `LinuxFileType.File` or `LinuxFileType.Directory`).
   */
  async stat(path) {
    if (!__privateGet(this, _supportsStat)) {
      throw new Error("Not supported");
    }
    return await adbSyncStat(this._socket, path);
  }
  /**
   * Checks if `path` is a directory, or a symbolic link to a directory.
   *
   * This uses `lstat` internally, thus works on all Android versions.
   */
  async isDirectory(path) {
    try {
      await this.lstat(path + "/");
      return true;
    } catch {
      return false;
    }
  }
  opendir(path) {
    return adbSyncOpenDir(this._socket, path, this.supportsListV2);
  }
  async readdir(path) {
    const results = [];
    for await (const entry of this.opendir(path)) {
      results.push(entry);
    }
    return results;
  }
  /**
   * Reads the content of a file on device.
   *
   * @param filename The full path of the file on device to read.
   * @returns A `ReadableStream` that contains the file content.
   */
  read(filename) {
    return adbSyncPull(this._socket, filename);
  }
  /**
   * Writes a file on device. If the file name already exists, it will be overwritten.
   *
   * @param options The content and options of the file to write.
   */
  async write(options) {
    if (this.needPushMkdirWorkaround) {
      await this._adb.subprocess.noneProtocol.spawnWait([
        "mkdir",
        "-p",
        escapeArg(dirname(options.filename))
      ]);
    }
    await adbSyncPush({
      v2: this.supportsSendReceiveV2,
      socket: this._socket,
      ...options
    });
  }
  lockSocket() {
    return this._socket.lock();
  }
  dispose() {
    return this._socket.close();
  }
};
_supportsStat = new WeakMap();
_supportsListV2 = new WeakMap();
_fixedPushMkdir = new WeakMap();
_supportsSendReceiveV2 = new WeakMap();
_needPushMkdirWorkaround = new WeakMap();

// node_modules/@yume-chan/adb/esm/commands/tcpip.js
function parsePort(value) {
  if (!value || value === "0") {
    return void 0;
  }
  return Number.parseInt(value, 10);
}
var AdbTcpIpService = class extends AdbServiceBase {
  async getListenAddresses() {
    const serviceListenAddresses = await this.adb.getProp("service.adb.listen_addrs");
    const servicePort = await this.adb.getProp("service.adb.tcp.port");
    const persistPort = await this.adb.getProp("persist.adb.tcp.port");
    return {
      serviceListenAddresses: serviceListenAddresses != "" ? serviceListenAddresses.split(",") : [],
      servicePort: parsePort(servicePort),
      persistPort: parsePort(persistPort)
    };
  }
  async setPort(port) {
    if (port <= 0) {
      throw new TypeError(`Invalid port ${port}`);
    }
    const output = await this.adb.createSocketAndWait(`tcpip:${port}`);
    if (output !== `restarting in TCP mode port: ${port}
`) {
      throw new Error(output);
    }
    return output;
  }
  async disable() {
    const output = await this.adb.createSocketAndWait("usb:");
    if (output !== "restarting in USB mode\n") {
      throw new Error(output);
    }
    return output;
  }
};

// node_modules/@yume-chan/adb/esm/adb.js
var _transport;
var Adb = class {
  constructor(transport) {
    __privateAdd(this, _transport);
    __publicField(this, "subprocess");
    __publicField(this, "power");
    __publicField(this, "reverse");
    __publicField(this, "tcpip");
    __privateSet(this, _transport, transport);
    this.subprocess = new AdbSubprocessService(this);
    this.power = new AdbPower(this);
    this.reverse = new AdbReverseService(this);
    this.tcpip = new AdbTcpIpService(this);
  }
  get transport() {
    return __privateGet(this, _transport);
  }
  get serial() {
    return __privateGet(this, _transport).serial;
  }
  get maxPayloadSize() {
    return __privateGet(this, _transport).maxPayloadSize;
  }
  get banner() {
    return __privateGet(this, _transport).banner;
  }
  get disconnected() {
    return __privateGet(this, _transport).disconnected;
  }
  get clientFeatures() {
    return __privateGet(this, _transport).clientFeatures;
  }
  get deviceFeatures() {
    return this.banner.features;
  }
  canUseFeature(feature) {
    return this.clientFeatures.includes(feature) && this.deviceFeatures.includes(feature);
  }
  /**
   * Creates a new ADB Socket to the specified service or socket address.
   */
  async createSocket(service) {
    return __privateGet(this, _transport).connect(service);
  }
  async createSocketAndWait(service) {
    const socket = await this.createSocket(service);
    return await socket.readable.pipeThrough(new TextDecoderStream()).pipeThrough(new ConcatStringStream());
  }
  getProp(key) {
    return this.subprocess.noneProtocol.spawnWaitText(["getprop", key]).then((output) => output.trim());
  }
  rm(filenames, options) {
    const args = ["rm"];
    if (options?.recursive) {
      args.push("-r");
    }
    if (options?.force) {
      args.push("-f");
    }
    if (Array.isArray(filenames)) {
      for (const filename of filenames) {
        args.push(escapeArg(filename));
      }
    } else {
      args.push(escapeArg(filenames));
    }
    args.push("</dev/null");
    return this.subprocess.noneProtocol.spawnWaitText(args);
  }
  async sync() {
    const socket = await this.createSocket("sync:");
    return new AdbSync(this, socket);
  }
  async framebuffer() {
    return framebuffer(this);
  }
  async close() {
    await __privateGet(this, _transport).close();
  }
};
_transport = new WeakMap();

// node_modules/@yume-chan/adb/esm/banner.js
var AdbBannerKey = {
  Product: "ro.product.name",
  Model: "ro.product.model",
  Device: "ro.product.device",
  Features: "features"
};
var _state2, _product, _model, _device, _features;
var _AdbBanner = class _AdbBanner {
  // eslint-disable-next-line @typescript-eslint/max-params
  constructor(state, product, model, device, features) {
    __privateAdd(this, _state2);
    __privateAdd(this, _product);
    __privateAdd(this, _model);
    __privateAdd(this, _device);
    __privateAdd(this, _features, []);
    __privateSet(this, _state2, state);
    __privateSet(this, _product, product);
    __privateSet(this, _model, model);
    __privateSet(this, _device, device);
    __privateSet(this, _features, features);
  }
  static parse(banner) {
    let state;
    let product;
    let model;
    let device;
    let features = [];
    const pieces = banner.split("::");
    if (pieces.length > 1) {
      state = pieces[0].trim() || void 0;
      const props = pieces[1];
      for (const prop of props.split(";")) {
        if (!prop) {
          continue;
        }
        const keyValue = prop.split("=");
        if (keyValue.length !== 2) {
          continue;
        }
        const [key, value] = keyValue;
        switch (key) {
          case AdbBannerKey.Product:
            product = value;
            break;
          case AdbBannerKey.Model:
            model = value;
            break;
          case AdbBannerKey.Device:
            device = value;
            break;
          case AdbBannerKey.Features:
            features = value.split(",");
            break;
        }
      }
    }
    return new _AdbBanner(state, product, model, device, features);
  }
  get state() {
    return __privateGet(this, _state2);
  }
  get product() {
    return __privateGet(this, _product);
  }
  get model() {
    return __privateGet(this, _model);
  }
  get device() {
    return __privateGet(this, _device);
  }
  get features() {
    return __privateGet(this, _features);
  }
};
_state2 = new WeakMap();
_product = new WeakMap();
_model = new WeakMap();
_device = new WeakMap();
_features = new WeakMap();
var AdbBanner = _AdbBanner;

// node_modules/@yume-chan/adb/esm/daemon/crypto.js
function getBigUint(array, byteOffset, length) {
  let result = 0n;
  for (let i2 = byteOffset; i2 < byteOffset + length; i2 += 8) {
    result <<= 64n;
    const value = getUint64BigEndian(array, i2);
    result |= value;
  }
  return result;
}
function setBigUint(array, byteOffset, length, value, littleEndian) {
  if (littleEndian) {
    while (value > 0n) {
      setInt64LittleEndian(array, byteOffset, value);
      byteOffset += 8;
      value >>= 64n;
    }
  } else {
    let position = byteOffset + length - 8;
    while (value > 0n) {
      setInt64BigEndian(array, position, value);
      position -= 8;
      value >>= 64n;
    }
  }
}
var RsaPrivateKeyNOffset = 38;
var RsaPrivateKeyNLength = 2048 / 8;
var RsaPrivateKeyDOffset = 303;
var RsaPrivateKeyDLength = 2048 / 8;
function rsaParsePrivateKey(key) {
  const n2 = getBigUint(key, RsaPrivateKeyNOffset, RsaPrivateKeyNLength);
  const d2 = getBigUint(key, RsaPrivateKeyDOffset, RsaPrivateKeyDLength);
  return [n2, d2];
}
function nonNegativeMod(m2, d2) {
  const r2 = m2 % d2;
  if (r2 > 0) {
    return r2;
  }
  return r2 + (d2 > 0 ? d2 : -d2);
}
function modInverse(a2, m2) {
  a2 = nonNegativeMod(a2, m2);
  if (!a2 || m2 < 2) {
    return NaN;
  }
  const s2 = [];
  let b2 = m2;
  while (b2) {
    [a2, b2] = [b2, a2 % b2];
    s2.push({ a: a2, b: b2 });
  }
  if (a2 !== 1) {
    return NaN;
  }
  let x2 = 1;
  let y2 = 0;
  for (let i2 = s2.length - 2; i2 >= 0; i2 -= 1) {
    [x2, y2] = [y2, x2 - y2 * Math.floor(s2[i2].a / s2[i2].b)];
  }
  return nonNegativeMod(y2, m2);
}
var ModulusLengthInBytes = 2048 / 8;
var ModulusLengthInWords = ModulusLengthInBytes / 4;
function adbGetPublicKeySize() {
  return 4 + 4 + ModulusLengthInBytes + ModulusLengthInBytes + 4;
}
function adbGeneratePublicKey(privateKey, output) {
  let outputType;
  const outputLength = adbGetPublicKeySize();
  if (!output) {
    output = new Uint8Array(outputLength);
    outputType = "Uint8Array";
  } else {
    if (output.length < outputLength) {
      throw new TypeError("output buffer is too small");
    }
    outputType = "number";
  }
  const outputView = new DataView(output.buffer, output.byteOffset, output.length);
  let outputOffset = 0;
  outputView.setUint32(outputOffset, ModulusLengthInWords, true);
  outputOffset += 4;
  const [n2] = rsaParsePrivateKey(privateKey);
  const n0inv = -modInverse(Number(n2 % 2n ** 32n), 2 ** 32);
  outputView.setInt32(outputOffset, n0inv, true);
  outputOffset += 4;
  setBigUint(output, outputOffset, ModulusLengthInBytes, n2, true);
  outputOffset += ModulusLengthInBytes;
  const rr2 = 2n ** 4096n % n2;
  setBigUint(output, outputOffset, ModulusLengthInBytes, rr2, true);
  outputOffset += ModulusLengthInBytes;
  outputView.setUint32(outputOffset, 65537, true);
  outputOffset += 4;
  if (outputType === "Uint8Array") {
    return output;
  } else {
    return outputLength;
  }
}
function powMod(base, exponent, modulus) {
  if (modulus === 1n) {
    return 0n;
  }
  let r2 = 1n;
  base = base % modulus;
  while (exponent > 0n) {
    if (BigInt.asUintN(1, exponent) === 1n) {
      r2 = r2 * base % modulus;
    }
    base = base * base % modulus;
    exponent >>= 1n;
  }
  return r2;
}
var SHA1_DIGEST_LENGTH = 20;
var ASN1_SEQUENCE = 48;
var ASN1_OCTET_STRING = 4;
var ASN1_NULL = 5;
var ASN1_OID = 6;
var SHA1_DIGEST_INFO = new Uint8Array([
  ASN1_SEQUENCE,
  13 + SHA1_DIGEST_LENGTH,
  ASN1_SEQUENCE,
  9,
  // SHA-1 (1 3 14 3 2 26)
  ASN1_OID,
  5,
  1 * 40 + 3,
  14,
  3,
  2,
  26,
  ASN1_NULL,
  0,
  ASN1_OCTET_STRING,
  SHA1_DIGEST_LENGTH
]);
function rsaSign(privateKey, data) {
  const [n2, d2] = rsaParsePrivateKey(privateKey);
  const padded = new Uint8Array(256);
  let index = 0;
  padded[index] = 0;
  index += 1;
  padded[index] = 1;
  index += 1;
  const fillLength = padded.length - SHA1_DIGEST_INFO.length - data.length - 1;
  while (index < fillLength) {
    padded[index] = 255;
    index += 1;
  }
  padded[index] = 0;
  index += 1;
  padded.set(SHA1_DIGEST_INFO, index);
  index += SHA1_DIGEST_INFO.length;
  padded.set(data, index);
  const signature = powMod(getBigUint(padded, 0, padded.length), d2, n2);
  setBigUint(padded, 0, padded.length, signature, false);
  return padded;
}

// node_modules/@yume-chan/adb/esm/daemon/packet.js
var AdbCommand = {
  Auth: 1213486401,
  // 'AUTH'
  Close: 1163086915,
  // 'CLSE'
  Connect: 1314410051,
  // 'CNXN'
  Okay: 1497451343,
  // 'OKAY'
  Open: 1313165391,
  // 'OPEN'
  Write: 1163154007
  // 'WRTE'
};
var AdbPacketHeader = struct({
  command: u32,
  arg0: u32,
  arg1: u32,
  payloadLength: u32,
  checksum: u32,
  magic: s32
}, { littleEndian: true });
var AdbPacket = extend(AdbPacketHeader, {
  payload: buffer("payloadLength")
});
function calculateChecksum(payload) {
  return payload.reduce((result, item) => result + item, 0);
}

// node_modules/@yume-chan/adb/esm/daemon/auth.js
var AdbAuthType = {
  Token: 1,
  Signature: 2,
  PublicKey: 3
};
var AdbSignatureAuthenticator = async function* (credentialStore, getNextRequest) {
  for await (const key of credentialStore.iterateKeys()) {
    const packet = await getNextRequest();
    if (packet.arg0 !== AdbAuthType.Token) {
      return;
    }
    const signature = rsaSign(key.buffer, packet.payload);
    yield {
      command: AdbCommand.Auth,
      arg0: AdbAuthType.Signature,
      arg1: 0,
      payload: signature
    };
  }
};
var AdbPublicKeyAuthenticator = async function* (credentialStore, getNextRequest) {
  const packet = await getNextRequest();
  if (packet.arg0 !== AdbAuthType.Token) {
    return;
  }
  let privateKey;
  for await (const key of credentialStore.iterateKeys()) {
    privateKey = key;
    break;
  }
  if (!privateKey) {
    privateKey = await credentialStore.generateKey();
  }
  const publicKeyLength = adbGetPublicKeySize();
  const [publicKeyBase64Length] = calculateBase64EncodedLength(publicKeyLength);
  const nameBuffer = privateKey.name?.length ? encodeUtf8(privateKey.name) : EmptyUint8Array;
  const publicKeyBuffer = new Uint8Array(publicKeyBase64Length + (nameBuffer.length ? nameBuffer.length + 1 : 0) + // Space character + name
  1);
  adbGeneratePublicKey(privateKey.buffer, publicKeyBuffer);
  encodeBase64(publicKeyBuffer.subarray(0, publicKeyLength), publicKeyBuffer);
  if (nameBuffer.length) {
    publicKeyBuffer[publicKeyBase64Length] = 32;
    publicKeyBuffer.set(nameBuffer, publicKeyBase64Length + 1);
  }
  yield {
    command: AdbCommand.Auth,
    arg0: AdbAuthType.PublicKey,
    arg1: 0,
    payload: publicKeyBuffer
  };
};
var ADB_DEFAULT_AUTHENTICATORS = [
  AdbSignatureAuthenticator,
  AdbPublicKeyAuthenticator
];
var _credentialStore, _pendingRequest, _iterator, _getNextRequest, _AdbAuthenticationProcessor_instances, invokeAuthenticator_fn;
var AdbAuthenticationProcessor = class {
  constructor(authenticators, credentialStore) {
    __privateAdd(this, _AdbAuthenticationProcessor_instances);
    __publicField(this, "authenticators");
    __privateAdd(this, _credentialStore);
    __privateAdd(this, _pendingRequest, new PromiseResolver());
    __privateAdd(this, _iterator);
    __privateAdd(this, _getNextRequest, () => {
      return __privateGet(this, _pendingRequest).promise;
    });
    this.authenticators = authenticators;
    __privateSet(this, _credentialStore, credentialStore);
  }
  async process(packet) {
    if (!__privateGet(this, _iterator)) {
      __privateSet(this, _iterator, __privateMethod(this, _AdbAuthenticationProcessor_instances, invokeAuthenticator_fn).call(this));
    }
    __privateGet(this, _pendingRequest).resolve(packet);
    const result = await __privateGet(this, _iterator).next();
    if (result.done) {
      throw new Error("No authenticator can handle the request");
    }
    return result.value;
  }
  dispose() {
    void __privateGet(this, _iterator)?.return?.();
  }
};
_credentialStore = new WeakMap();
_pendingRequest = new WeakMap();
_iterator = new WeakMap();
_getNextRequest = new WeakMap();
_AdbAuthenticationProcessor_instances = new WeakSet();
invokeAuthenticator_fn = async function* () {
  for (const authenticator of this.authenticators) {
    for await (const packet of authenticator(__privateGet(this, _credentialStore), __privateGet(this, _getNextRequest))) {
      __privateSet(this, _pendingRequest, new PromiseResolver());
      yield packet;
    }
  }
};

// node_modules/@yume-chan/adb/esm/daemon/socket.js
var _dispatcher, _readable5, _readableController3, _writableController, _closed, _closedPromise, _socket6, _availableWriteBytesChanged, _availableWriteBytes, _AdbDaemonSocketController_instances, writeChunk_fn;
var AdbDaemonSocketController = class {
  constructor(options) {
    __privateAdd(this, _AdbDaemonSocketController_instances);
    __privateAdd(this, _dispatcher);
    __publicField(this, "localId");
    __publicField(this, "remoteId");
    __publicField(this, "localCreated");
    __publicField(this, "service");
    __privateAdd(this, _readable5);
    __privateAdd(this, _readableController3);
    __privateAdd(this, _writableController);
    __publicField(this, "writable");
    __privateAdd(this, _closed, false);
    __privateAdd(this, _closedPromise, new PromiseResolver());
    __privateAdd(this, _socket6);
    __privateAdd(this, _availableWriteBytesChanged);
    /**
     * When delayed ack is disabled, returns `Infinity` if the socket is ready to write
     * (exactly one packet can be written no matter how large it is), or `-1` if the socket
     * is waiting for ack message.
     *
     * When delayed ack is enabled, returns a non-negative finite number indicates the number of
     * bytes that can be written to the socket before waiting for ack message.
     */
    __privateAdd(this, _availableWriteBytes, 0);
    __privateSet(this, _dispatcher, options.dispatcher);
    this.localId = options.localId;
    this.remoteId = options.remoteId;
    this.localCreated = options.localCreated;
    this.service = options.service;
    __privateSet(this, _readable5, new PushReadableStream((controller) => {
      __privateSet(this, _readableController3, controller);
    }));
    this.writable = new maybe_consumable_exports.WritableStream({
      start: (controller) => {
        __privateSet(this, _writableController, controller);
        controller.signal.addEventListener("abort", () => {
          __privateGet(this, _availableWriteBytesChanged)?.reject(controller.signal.reason);
        });
      },
      write: async (data) => {
        const size = data.length;
        const chunkSize = __privateGet(this, _dispatcher).options.maxPayloadSize;
        for (let start = 0, end = chunkSize; start < size; start = end, end += chunkSize) {
          const chunk = data.subarray(start, end);
          await __privateMethod(this, _AdbDaemonSocketController_instances, writeChunk_fn).call(this, chunk);
        }
      }
    });
    __privateSet(this, _socket6, new AdbDaemonSocket(this));
    __privateSet(this, _availableWriteBytes, options.availableWriteBytes);
  }
  get readable() {
    return __privateGet(this, _readable5);
  }
  get closed() {
    return __privateGet(this, _closedPromise).promise;
  }
  get socket() {
    return __privateGet(this, _socket6);
  }
  async enqueue(data) {
    await __privateGet(this, _readableController3).enqueue(data);
  }
  ack(bytes) {
    __privateSet(this, _availableWriteBytes, __privateGet(this, _availableWriteBytes) + bytes);
    __privateGet(this, _availableWriteBytesChanged)?.resolve();
  }
  async close() {
    if (__privateGet(this, _closed)) {
      return;
    }
    __privateSet(this, _closed, true);
    __privateGet(this, _availableWriteBytesChanged)?.reject(new Error("Socket closed"));
    try {
      __privateGet(this, _writableController).error(new Error("Socket closed"));
    } catch {
    }
    await __privateGet(this, _dispatcher).sendPacket(AdbCommand.Close, this.localId, this.remoteId, EmptyUint8Array);
  }
  dispose() {
    __privateGet(this, _readableController3).close();
    __privateGet(this, _closedPromise).resolve(void 0);
  }
};
_dispatcher = new WeakMap();
_readable5 = new WeakMap();
_readableController3 = new WeakMap();
_writableController = new WeakMap();
_closed = new WeakMap();
_closedPromise = new WeakMap();
_socket6 = new WeakMap();
_availableWriteBytesChanged = new WeakMap();
_availableWriteBytes = new WeakMap();
_AdbDaemonSocketController_instances = new WeakSet();
writeChunk_fn = async function(data) {
  const length = data.length;
  while (__privateGet(this, _availableWriteBytes) < length) {
    const resolver = new PromiseResolver();
    __privateSet(this, _availableWriteBytesChanged, resolver);
    await resolver.promise;
  }
  if (__privateGet(this, _availableWriteBytes) === Infinity) {
    __privateSet(this, _availableWriteBytes, -1);
  } else {
    __privateSet(this, _availableWriteBytes, __privateGet(this, _availableWriteBytes) - length);
  }
  await __privateGet(this, _dispatcher).sendPacket(AdbCommand.Write, this.localId, this.remoteId, data);
};
var _controller;
var AdbDaemonSocket = class {
  constructor(controller) {
    __privateAdd(this, _controller);
    __privateSet(this, _controller, controller);
  }
  get localId() {
    return __privateGet(this, _controller).localId;
  }
  get remoteId() {
    return __privateGet(this, _controller).remoteId;
  }
  get localCreated() {
    return __privateGet(this, _controller).localCreated;
  }
  get service() {
    return __privateGet(this, _controller).service;
  }
  get readable() {
    return __privateGet(this, _controller).readable;
  }
  get writable() {
    return __privateGet(this, _controller).writable;
  }
  get closed() {
    return __privateGet(this, _controller).closed;
  }
  close() {
    return __privateGet(this, _controller).close();
  }
};
_controller = new WeakMap();

// node_modules/@yume-chan/adb/esm/daemon/dispatcher.js
var _initializers, _sockets, _writer5, _closed2, _disconnected, _incomingSocketHandlers, _readAbortController, _AdbPacketDispatcher_instances, handleClose_fn, handleOkay_fn, sendOkay_fn, handleOpen_fn, handleWrite_fn, dispose_fn;
var AdbPacketDispatcher = class {
  constructor(connection, options) {
    __privateAdd(this, _AdbPacketDispatcher_instances);
    // ADB socket id starts from 1
    // (0 means open failed)
    __privateAdd(this, _initializers, new AsyncOperationManager(1));
    /**
     * Socket local ID to the socket controller.
     */
    __privateAdd(this, _sockets, /* @__PURE__ */ new Map());
    __privateAdd(this, _writer5);
    __publicField(this, "options");
    __privateAdd(this, _closed2, false);
    __privateAdd(this, _disconnected, new PromiseResolver());
    __privateAdd(this, _incomingSocketHandlers, /* @__PURE__ */ new Map());
    __privateAdd(this, _readAbortController, new AbortController2());
    this.options = options;
    if (this.options.initialDelayedAckBytes < 0) {
      this.options.initialDelayedAckBytes = 0;
    }
    connection.readable.pipeTo(new WritableStream({
      write: async (packet, controller) => {
        switch (packet.command) {
          case AdbCommand.Close:
            await __privateMethod(this, _AdbPacketDispatcher_instances, handleClose_fn).call(this, packet);
            break;
          case AdbCommand.Okay:
            __privateMethod(this, _AdbPacketDispatcher_instances, handleOkay_fn).call(this, packet);
            break;
          case AdbCommand.Open:
            await __privateMethod(this, _AdbPacketDispatcher_instances, handleOpen_fn).call(this, packet);
            break;
          case AdbCommand.Write:
            __privateMethod(this, _AdbPacketDispatcher_instances, handleWrite_fn).call(this, packet).catch((e2) => {
              controller.error(e2);
            });
            break;
          default:
            throw new Error(`Unknown command: ${packet.command.toString(16)}`);
        }
      }
    }), {
      preventCancel: options.preserveConnection ?? false,
      signal: __privateGet(this, _readAbortController).signal
    }).then(() => {
      __privateMethod(this, _AdbPacketDispatcher_instances, dispose_fn).call(this);
    }, (e2) => {
      if (!__privateGet(this, _closed2)) {
        __privateGet(this, _disconnected).reject(e2);
      }
      __privateMethod(this, _AdbPacketDispatcher_instances, dispose_fn).call(this);
    });
    __privateSet(this, _writer5, connection.writable.getWriter());
  }
  get disconnected() {
    return __privateGet(this, _disconnected).promise;
  }
  async createSocket(service) {
    if (this.options.appendNullToServiceString) {
      service += "\0";
    }
    const [localId, initializer] = __privateGet(this, _initializers).add();
    await this.sendPacket(AdbCommand.Open, localId, this.options.initialDelayedAckBytes, service);
    const { remoteId, availableWriteBytes } = await initializer;
    const controller = new AdbDaemonSocketController({
      dispatcher: this,
      localId,
      remoteId,
      localCreated: true,
      service,
      availableWriteBytes
    });
    __privateGet(this, _sockets).set(localId, controller);
    return controller.socket;
  }
  addReverseTunnel(service, handler) {
    __privateGet(this, _incomingSocketHandlers).set(service, handler);
  }
  removeReverseTunnel(address) {
    __privateGet(this, _incomingSocketHandlers).delete(address);
  }
  clearReverseTunnels() {
    __privateGet(this, _incomingSocketHandlers).clear();
  }
  async sendPacket(command, arg0, arg1, payload) {
    if (typeof payload === "string") {
      payload = encodeUtf8(payload);
    }
    if (payload.length > this.options.maxPayloadSize) {
      throw new TypeError("payload too large");
    }
    await Consumable.WritableStream.write(__privateGet(this, _writer5), {
      command,
      arg0,
      arg1,
      payload,
      checksum: this.options.calculateChecksum ? calculateChecksum(payload) : 0,
      magic: command ^ 4294967295
    });
  }
  async close() {
    await Promise.all(Array.from(__privateGet(this, _sockets).values(), (socket) => socket.close()));
    __privateSet(this, _closed2, true);
    __privateGet(this, _readAbortController).abort();
    if (this.options.preserveConnection) {
      __privateGet(this, _writer5).releaseLock();
    } else {
      await __privateGet(this, _writer5).close();
    }
  }
};
_initializers = new WeakMap();
_sockets = new WeakMap();
_writer5 = new WeakMap();
_closed2 = new WeakMap();
_disconnected = new WeakMap();
_incomingSocketHandlers = new WeakMap();
_readAbortController = new WeakMap();
_AdbPacketDispatcher_instances = new WeakSet();
handleClose_fn = async function(packet) {
  if (packet.arg0 === 0 && __privateGet(this, _initializers).reject(packet.arg1, new Error("Socket open failed"))) {
    return;
  }
  const socket = __privateGet(this, _sockets).get(packet.arg1);
  if (socket) {
    await socket.close();
    socket.dispose();
    __privateGet(this, _sockets).delete(packet.arg1);
    return;
  }
};
handleOkay_fn = function(packet) {
  let ackBytes;
  if (this.options.initialDelayedAckBytes !== 0) {
    if (packet.payload.length !== 4) {
      throw new Error("Invalid OKAY packet. Payload size should be 4");
    }
    ackBytes = getUint32LittleEndian(packet.payload, 0);
  } else {
    if (packet.payload.length !== 0) {
      throw new Error("Invalid OKAY packet. Payload size should be 0");
    }
    ackBytes = Infinity;
  }
  if (__privateGet(this, _initializers).resolve(packet.arg1, {
    remoteId: packet.arg0,
    availableWriteBytes: ackBytes
  })) {
    return;
  }
  const socket = __privateGet(this, _sockets).get(packet.arg1);
  if (socket) {
    socket.ack(ackBytes);
    return;
  }
  void this.sendPacket(AdbCommand.Close, packet.arg1, packet.arg0, EmptyUint8Array);
};
sendOkay_fn = function(localId, remoteId, ackBytes) {
  let payload;
  if (this.options.initialDelayedAckBytes !== 0) {
    payload = new Uint8Array(4);
    setUint32LittleEndian(payload, 0, ackBytes);
  } else {
    payload = EmptyUint8Array;
  }
  return this.sendPacket(AdbCommand.Okay, localId, remoteId, payload);
};
handleOpen_fn = async function(packet) {
  const [localId] = __privateGet(this, _initializers).add();
  __privateGet(this, _initializers).resolve(localId, void 0);
  const remoteId = packet.arg0;
  let availableWriteBytes = packet.arg1;
  let service = decodeUtf8(packet.payload);
  if (service.endsWith("\0")) {
    service = service.substring(0, service.length - 1);
  }
  if (this.options.initialDelayedAckBytes === 0) {
    if (availableWriteBytes !== 0) {
      throw new Error("Invalid OPEN packet. arg1 should be 0");
    }
    availableWriteBytes = Infinity;
  } else {
    if (availableWriteBytes === 0) {
      throw new Error("Invalid OPEN packet. arg1 should be greater than 0");
    }
  }
  const handler = __privateGet(this, _incomingSocketHandlers).get(service);
  if (!handler) {
    await this.sendPacket(AdbCommand.Close, 0, remoteId, EmptyUint8Array);
    return;
  }
  const controller = new AdbDaemonSocketController({
    dispatcher: this,
    localId,
    remoteId,
    localCreated: false,
    service,
    availableWriteBytes
  });
  try {
    await handler(controller.socket);
    __privateGet(this, _sockets).set(localId, controller);
    await __privateMethod(this, _AdbPacketDispatcher_instances, sendOkay_fn).call(this, localId, remoteId, this.options.initialDelayedAckBytes);
  } catch {
    await this.sendPacket(AdbCommand.Close, 0, remoteId, EmptyUint8Array);
  }
};
handleWrite_fn = async function(packet) {
  const socket = __privateGet(this, _sockets).get(packet.arg1);
  if (!socket) {
    throw new Error(`Unknown local socket id: ${packet.arg1}`);
  }
  let handled = false;
  const promises = [
    (async () => {
      await socket.enqueue(packet.payload);
      await __privateMethod(this, _AdbPacketDispatcher_instances, sendOkay_fn).call(this, packet.arg1, packet.arg0, packet.payload.length);
      handled = true;
    })()
  ];
  if (this.options.readTimeLimit) {
    promises.push((async () => {
      await delay(this.options.readTimeLimit);
      if (!handled) {
        throw new Error(`readable of \`${socket.service}\` has stalled for ${this.options.readTimeLimit} milliseconds`);
      }
    })());
  }
  await Promise.race(promises);
};
dispose_fn = function() {
  for (const socket of __privateGet(this, _sockets).values()) {
    socket.dispose();
  }
  __privateGet(this, _disconnected).resolve();
};

// node_modules/@yume-chan/adb/esm/daemon/transport.js
var ADB_DAEMON_VERSION_OMIT_CHECKSUM = 16777217;
var ADB_DAEMON_DEFAULT_FEATURES = /* @__PURE__ */ (() => [
  AdbFeature.ShellV2,
  AdbFeature.Cmd,
  AdbFeature.StatV2,
  AdbFeature.ListV2,
  AdbFeature.FixedPushMkdir,
  "apex",
  AdbFeature.Abb,
  // only tells the client the symlink timestamp issue in `adb push --sync` has been fixed.
  // No special handling required.
  "fixed_push_symlink_timestamp",
  AdbFeature.AbbExec,
  "remount_shell",
  "track_app",
  AdbFeature.SendReceiveV2,
  "sendrecv_v2_brotli",
  "sendrecv_v2_lz4",
  "sendrecv_v2_zstd",
  "sendrecv_v2_dry_run_send",
  AdbFeature.DelayedAck
])();
var ADB_DAEMON_DEFAULT_INITIAL_PAYLOAD_SIZE = 32 * 1024 * 1024;
var _connection, _dispatcher2, _serial, _protocolVersion, _banner, _clientFeatures;
var _AdbDaemonTransport = class _AdbDaemonTransport {
  constructor({ serial, connection, version, banner, features = ADB_DAEMON_DEFAULT_FEATURES, initialDelayedAckBytes, ...options }) {
    __privateAdd(this, _connection);
    __privateAdd(this, _dispatcher2);
    __privateAdd(this, _serial);
    __privateAdd(this, _protocolVersion);
    __privateAdd(this, _banner);
    __privateAdd(this, _clientFeatures);
    __privateSet(this, _serial, serial);
    __privateSet(this, _connection, connection);
    __privateSet(this, _banner, AdbBanner.parse(banner));
    __privateSet(this, _clientFeatures, features);
    if (features.includes(AdbFeature.DelayedAck)) {
      if (initialDelayedAckBytes <= 0) {
        throw new TypeError("`initialDelayedAckBytes` must be greater than 0 when DelayedAck feature is enabled.");
      }
      if (!__privateGet(this, _banner).features.includes(AdbFeature.DelayedAck)) {
        initialDelayedAckBytes = 0;
      }
    } else {
      initialDelayedAckBytes = 0;
    }
    let calculateChecksum3;
    let appendNullToServiceString;
    if (version >= ADB_DAEMON_VERSION_OMIT_CHECKSUM) {
      calculateChecksum3 = false;
      appendNullToServiceString = false;
    } else {
      calculateChecksum3 = true;
      appendNullToServiceString = true;
    }
    __privateSet(this, _dispatcher2, new AdbPacketDispatcher(connection, {
      calculateChecksum: calculateChecksum3,
      appendNullToServiceString,
      initialDelayedAckBytes,
      ...options
    }));
    __privateSet(this, _protocolVersion, version);
  }
  /**
   * Authenticate with the ADB Daemon and create a new transport.
   */
  static async authenticate({ serial, connection, credentialStore, authenticators = ADB_DEFAULT_AUTHENTICATORS, features = ADB_DAEMON_DEFAULT_FEATURES, initialDelayedAckBytes = ADB_DAEMON_DEFAULT_INITIAL_PAYLOAD_SIZE, ...options }) {
    let version = 16777217;
    let maxPayloadSize = 1024 * 1024;
    const resolver = new PromiseResolver();
    const authProcessor = new AdbAuthenticationProcessor(authenticators, credentialStore);
    const abortController = new AbortController2();
    const pipe = connection.readable.pipeTo(new WritableStream({
      async write(packet) {
        switch (packet.command) {
          case AdbCommand.Connect:
            version = Math.min(version, packet.arg0);
            maxPayloadSize = Math.min(maxPayloadSize, packet.arg1);
            resolver.resolve(decodeUtf8(packet.payload));
            break;
          case AdbCommand.Auth: {
            const response = await authProcessor.process(packet);
            await sendPacket(response);
            break;
          }
          default:
            break;
        }
      }
    }), {
      // Don't cancel the source ReadableStream on AbortSignal abort.
      preventCancel: true,
      signal: abortController.signal
    }).then(() => {
      resolver.reject(new Error("Connection closed unexpectedly"));
    }, (e2) => {
      resolver.reject(e2);
    });
    const writer = connection.writable.getWriter();
    async function sendPacket(init) {
      init.checksum = calculateChecksum(init.payload);
      init.magic = init.command ^ 4294967295;
      await Consumable.WritableStream.write(writer, init);
    }
    const actualFeatures = features.slice();
    if (initialDelayedAckBytes <= 0) {
      const index = features.indexOf(AdbFeature.DelayedAck);
      if (index !== -1) {
        actualFeatures.splice(index, 1);
      }
    }
    let banner;
    try {
      await sendPacket({
        command: AdbCommand.Connect,
        arg0: version,
        arg1: maxPayloadSize,
        // The terminating `;` is required in formal definition
        // But ADB daemon (all versions) can still work without it
        payload: encodeUtf8(`host::features=${actualFeatures.join(",")}`)
      });
      banner = await resolver.promise;
    } finally {
      abortController.abort();
      writer.releaseLock();
      await pipe;
    }
    return new _AdbDaemonTransport({
      serial,
      connection,
      version,
      maxPayloadSize,
      banner,
      features: actualFeatures,
      initialDelayedAckBytes,
      ...options
    });
  }
  get connection() {
    return __privateGet(this, _connection);
  }
  get serial() {
    return __privateGet(this, _serial);
  }
  get protocolVersion() {
    return __privateGet(this, _protocolVersion);
  }
  get maxPayloadSize() {
    return __privateGet(this, _dispatcher2).options.maxPayloadSize;
  }
  get banner() {
    return __privateGet(this, _banner);
  }
  get disconnected() {
    return __privateGet(this, _dispatcher2).disconnected;
  }
  get clientFeatures() {
    return __privateGet(this, _clientFeatures);
  }
  connect(service) {
    return __privateGet(this, _dispatcher2).createSocket(service);
  }
  addReverseTunnel(handler, address) {
    if (!address) {
      const id = Math.random().toString().substring(2);
      address = `localabstract:reverse_${id}`;
    }
    __privateGet(this, _dispatcher2).addReverseTunnel(address, handler);
    return address;
  }
  removeReverseTunnel(address) {
    __privateGet(this, _dispatcher2).removeReverseTunnel(address);
  }
  clearReverseTunnels() {
    __privateGet(this, _dispatcher2).clearReverseTunnels();
  }
  close() {
    return __privateGet(this, _dispatcher2).close();
  }
};
_connection = new WeakMap();
_dispatcher2 = new WeakMap();
_serial = new WeakMap();
_protocolVersion = new WeakMap();
_banner = new WeakMap();
_clientFeatures = new WeakMap();
var AdbDaemonTransport = _AdbDaemonTransport;

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/async/esm/promise-resolver.js
var PromiseResolver2 = (function() {
  function PromiseResolver3() {
    var _this = this;
    this._state = "running";
    this.resolve = function(value) {
      _this._resolve(value);
      _this._state = "resolved";
    };
    this.reject = function(reason) {
      _this._reject(reason);
      _this._state = "rejected";
    };
    this._promise = new Promise(function(resolve, reject) {
      _this._resolve = resolve;
      _this._reject = reject;
    });
  }
  Object.defineProperty(PromiseResolver3.prototype, "promise", {
    get: function() {
      return this._promise;
    },
    enumerable: false,
    configurable: true
  });
  Object.defineProperty(PromiseResolver3.prototype, "state", {
    get: function() {
      return this._state;
    },
    enumerable: false,
    configurable: true
  });
  return PromiseResolver3;
})();

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/async/esm/async-operation-manager.js
var AsyncOperationManager2 = (function() {
  function AsyncOperationManager3(startId) {
    if (startId === void 0) {
      startId = 0;
    }
    this.pendingResolvers = /* @__PURE__ */ new Map();
    this.nextId = startId;
  }
  AsyncOperationManager3.prototype.add = function() {
    var id = this.nextId++;
    var resolver = new PromiseResolver2();
    this.pendingResolvers.set(id, resolver);
    return [id, resolver.promise];
  };
  AsyncOperationManager3.prototype.getResolver = function(id) {
    if (!this.pendingResolvers.has(id)) {
      return null;
    }
    var resolver = this.pendingResolvers.get(id);
    this.pendingResolvers.delete(id);
    return resolver;
  };
  AsyncOperationManager3.prototype.resolve = function(id, result) {
    var resolver = this.getResolver(id);
    if (resolver !== null) {
      resolver.resolve(result);
      return true;
    }
    return false;
  };
  AsyncOperationManager3.prototype.reject = function(id, reason) {
    var resolver = this.getResolver(id);
    if (resolver !== null) {
      resolver.reject(reason);
      return true;
    }
    return false;
  };
  return AsyncOperationManager3;
})();

// node_modules/web-streams-polyfill/dist/ponyfill.mjs
function e() {
}
function t(e2) {
  return "object" == typeof e2 && null !== e2 || "function" == typeof e2;
}
var r = e;
function o(e2, t2) {
  try {
    Object.defineProperty(e2, "name", { value: t2, configurable: true });
  } catch (e3) {
  }
}
var n = Promise;
var i = Promise.resolve.bind(n);
var a = Promise.prototype.then;
var s = Promise.reject.bind(n);
var l = i;
function u(e2) {
  return new n(e2);
}
function c(e2) {
  return u((t2) => t2(e2));
}
function d(e2) {
  return s(e2);
}
function f(e2, t2, r2) {
  return a.call(e2, t2, r2);
}
function h(e2, t2, o2) {
  f(f(e2, t2, o2), void 0, r);
}
function b(e2, t2) {
  h(e2, t2);
}
function _(e2, t2) {
  h(e2, void 0, t2);
}
function m(e2, t2, r2) {
  return f(e2, t2, r2);
}
function p(e2) {
  f(e2, void 0, r);
}
var y = (e2) => {
  if ("function" == typeof queueMicrotask) y = queueMicrotask;
  else {
    const e3 = c(void 0);
    y = (t2) => f(e3, t2);
  }
  return y(e2);
};
function S(e2, t2, r2) {
  if ("function" != typeof e2) throw new TypeError("Argument is not a function");
  return Function.prototype.apply.call(e2, t2, r2);
}
function g(e2, t2, r2) {
  try {
    return c(S(e2, t2, r2));
  } catch (e3) {
    return d(e3);
  }
}
var v = class {
  constructor() {
    this._cursor = 0, this._size = 0, this._front = { _elements: [], _next: void 0 }, this._back = this._front, this._cursor = 0, this._size = 0;
  }
  get length() {
    return this._size;
  }
  push(e2) {
    const t2 = this._back;
    let r2 = t2;
    16383 === t2._elements.length && (r2 = { _elements: [], _next: void 0 }), t2._elements.push(e2), r2 !== t2 && (this._back = r2, t2._next = r2), ++this._size;
  }
  shift() {
    const e2 = this._front;
    let t2 = e2;
    const r2 = this._cursor;
    let o2 = r2 + 1;
    const n2 = e2._elements, i2 = n2[r2];
    return 16384 === o2 && (t2 = e2._next, o2 = 0), --this._size, this._cursor = o2, e2 !== t2 && (this._front = t2), n2[r2] = void 0, i2;
  }
  forEach(e2) {
    let t2 = this._cursor, r2 = this._front, o2 = r2._elements;
    for (; !(t2 === o2.length && void 0 === r2._next || t2 === o2.length && (r2 = r2._next, o2 = r2._elements, t2 = 0, 0 === o2.length)); ) e2(o2[t2]), ++t2;
  }
  peek() {
    const e2 = this._front, t2 = this._cursor;
    return e2._elements[t2];
  }
};
var w = /* @__PURE__ */ Symbol("[[AbortSteps]]");
var R = /* @__PURE__ */ Symbol("[[ErrorSteps]]");
var T = /* @__PURE__ */ Symbol("[[CancelSteps]]");
var P = /* @__PURE__ */ Symbol("[[PullSteps]]");
var C = /* @__PURE__ */ Symbol("[[CanPullSyncSteps]]");
var q = /* @__PURE__ */ Symbol("[[ReleaseSteps]]");
function E(e2, t2) {
  e2._ownerReadableStream = t2, t2._reader = e2, "readable" === t2._state ? j(e2) : "closed" === t2._state ? (function(e3) {
    j(e3), z(e3);
  })(e2) : k(e2, t2._storedError);
}
function W(e2, t2) {
  return Mr(e2._ownerReadableStream, t2);
}
function O(e2) {
  const t2 = e2._ownerReadableStream;
  "readable" === t2._state ? A(e2, new TypeError("Reader was released and can no longer be used to monitor the stream's closedness")) : (function(e3, t3) {
    k(e3, t3);
  })(e2, new TypeError("Reader was released and can no longer be used to monitor the stream's closedness")), t2._readableStreamController[q](), t2._reader = void 0, e2._ownerReadableStream = void 0;
}
function B(e2) {
  return new TypeError("Cannot " + e2 + " a stream using a released reader");
}
function j(e2) {
  e2._closedPromise = u((t2, r2) => {
    e2._closedPromise_resolve = t2, e2._closedPromise_reject = r2;
  });
}
function k(e2, t2) {
  j(e2), A(e2, t2);
}
function A(e2, t2) {
  void 0 !== e2._closedPromise_reject && (p(e2._closedPromise), e2._closedPromise_reject(t2), e2._closedPromise_resolve = void 0, e2._closedPromise_reject = void 0);
}
function z(e2) {
  void 0 !== e2._closedPromise_resolve && (e2._closedPromise_resolve(void 0), e2._closedPromise_resolve = void 0, e2._closedPromise_reject = void 0);
}
var D = Number.isFinite || function(e2) {
  return "number" == typeof e2 && isFinite(e2);
};
var F = Math.trunc || function(e2) {
  return e2 < 0 ? Math.ceil(e2) : Math.floor(e2);
};
function L(e2, t2) {
  if (void 0 !== e2 && ("object" != typeof (r2 = e2) && "function" != typeof r2)) throw new TypeError(`${t2} is not an object.`);
  var r2;
}
function I(e2, t2) {
  if ("function" != typeof e2) throw new TypeError(`${t2} is not a function.`);
}
function $(e2, t2) {
  if (!/* @__PURE__ */ (function(e3) {
    return "object" == typeof e3 && null !== e3 || "function" == typeof e3;
  })(e2)) throw new TypeError(`${t2} is not an object.`);
}
function M(e2, t2, r2) {
  if (void 0 === e2) throw new TypeError(`Parameter ${t2} is required in '${r2}'.`);
}
function Y(e2, t2, r2) {
  if (void 0 === e2) throw new TypeError(`${t2} is required in '${r2}'.`);
}
function x(e2) {
  return Number(e2);
}
function Q(e2) {
  return 0 === e2 ? 0 : e2;
}
function N(e2, t2) {
  const r2 = Number.MAX_SAFE_INTEGER;
  let o2 = Number(e2);
  if (o2 = Q(o2), !D(o2)) throw new TypeError(`${t2} is not a finite number`);
  if (o2 = (function(e3) {
    return Q(F(e3));
  })(o2), o2 < 0 || o2 > r2) throw new TypeError(`${t2} is outside the accepted range of 0 to ${r2}, inclusive`);
  return D(o2) && 0 !== o2 ? o2 : 0;
}
function H(e2, t2) {
  if (!Ir(e2)) throw new TypeError(`${t2} is not a ReadableStream.`);
}
function V(e2) {
  return new ReadableStreamDefaultReader(e2);
}
function U(e2, t2) {
  e2._reader._readRequests.push(t2);
}
function G(e2, t2, r2) {
  const o2 = e2._reader._readRequests.shift();
  r2 ? o2._closeSteps() : o2._chunkSteps(t2);
}
function X(e2) {
  return e2._reader._readRequests.length;
}
function J(e2) {
  const t2 = e2._reader;
  return void 0 !== t2 && !!ee(t2);
}
var ReadableStreamDefaultReader = class {
  constructor(e2) {
    if (M(e2, 1, "ReadableStreamDefaultReader"), H(e2, "First parameter"), $r(e2)) throw new TypeError("This stream has already been locked for exclusive reading by another reader");
    E(this, e2), this._readRequests = new v();
  }
  get closed() {
    return ee(this) ? this._closedPromise : d(ne("closed"));
  }
  cancel(e2 = void 0) {
    return ee(this) ? void 0 === this._ownerReadableStream ? d(B("cancel")) : W(this, e2) : d(ne("cancel"));
  }
  read() {
    if (!ee(this)) return d(ne("read"));
    if (void 0 === this._ownerReadableStream) return d(B("read from"));
    const e2 = re(this) ? new Z() : new K();
    return te(this, e2), e2._promise;
  }
  releaseLock() {
    if (!ee(this)) throw ne("releaseLock");
    void 0 !== this._ownerReadableStream && (function(e2) {
      O(e2);
      const t2 = new TypeError("Reader was released");
      oe(e2, t2);
    })(this);
  }
};
Object.defineProperties(ReadableStreamDefaultReader.prototype, { cancel: { enumerable: true }, read: { enumerable: true }, releaseLock: { enumerable: true }, closed: { enumerable: true } }), o(ReadableStreamDefaultReader.prototype.cancel, "cancel"), o(ReadableStreamDefaultReader.prototype.read, "read"), o(ReadableStreamDefaultReader.prototype.releaseLock, "releaseLock"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableStreamDefaultReader.prototype, Symbol.toStringTag, { value: "ReadableStreamDefaultReader", configurable: true });
var K = class {
  constructor() {
    this._promise = u((e2, t2) => {
      this._resolvePromise = e2, this._rejectPromise = t2;
    });
  }
  _chunkSteps(e2) {
    this._resolvePromise({ value: e2, done: false });
  }
  _closeSteps() {
    this._resolvePromise({ value: void 0, done: true });
  }
  _errorSteps(e2) {
    this._rejectPromise(e2);
  }
};
var Z = class {
  constructor() {
    this._promise = void 0;
  }
  _chunkSteps(e2) {
    this._promise = l({ value: e2, done: false });
  }
  _closeSteps() {
    this._promise = l({ value: void 0, done: true });
  }
  _errorSteps(e2) {
    this._promise = d(e2);
  }
};
function ee(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_readRequests") && e2 instanceof ReadableStreamDefaultReader);
}
function te(e2, t2) {
  const r2 = e2._ownerReadableStream;
  r2._disturbed = true, "closed" === r2._state ? t2._closeSteps() : "errored" === r2._state ? t2._errorSteps(r2._storedError) : r2._readableStreamController[P](t2);
}
function re(e2) {
  const t2 = e2._ownerReadableStream;
  return "closed" === t2._state || ("errored" === t2._state || t2._readableStreamController[C]());
}
function oe(e2, t2) {
  const r2 = e2._readRequests;
  e2._readRequests = new v(), r2.forEach((e3) => {
    e3._errorSteps(t2);
  });
}
function ne(e2) {
  return new TypeError(`ReadableStreamDefaultReader.prototype.${e2} can only be used on a ReadableStreamDefaultReader`);
}
var ie;
var ae;
var se;
function le(e2) {
  return e2.slice();
}
function ue(e2, t2, r2, o2, n2) {
  new Uint8Array(e2).set(new Uint8Array(r2, o2, n2), t2);
}
var ce = (e2) => (ce = "function" == typeof e2.transfer ? (e3) => e3.transfer() : "function" == typeof structuredClone ? (e3) => structuredClone(e3, { transfer: [e3] }) : (e3) => e3, ce(e2));
var de = (e2) => (de = "boolean" == typeof e2.detached ? (e3) => e3.detached : (e3) => 0 === e3.byteLength, de(e2));
function fe(e2, t2, r2) {
  if (e2.slice) return e2.slice(t2, r2);
  const o2 = r2 - t2, n2 = new ArrayBuffer(o2);
  return ue(n2, 0, e2, t2, o2), n2;
}
function he(e2, t2) {
  const r2 = e2[t2];
  if (null != r2) {
    if ("function" != typeof r2) throw new TypeError(`${String(t2)} is not a function`);
    return r2;
  }
}
function be(e2) {
  try {
    const t2 = e2.done, r2 = e2.value;
    return f(l(r2), (e3) => ({ done: t2, value: e3 }));
  } catch (e3) {
    return d(e3);
  }
}
var _e = null !== (se = null !== (ie = Symbol.asyncIterator) && void 0 !== ie ? ie : null === (ae = Symbol.for) || void 0 === ae ? void 0 : ae.call(Symbol, "Symbol.asyncIterator")) && void 0 !== se ? se : "@@asyncIterator";
function me(e2, r2 = "sync", o2) {
  if (void 0 === o2) if ("async" === r2) {
    if (void 0 === (o2 = he(e2, _e))) {
      return (function(e3) {
        const r3 = { next() {
          let t2;
          try {
            t2 = pe(e3);
          } catch (e4) {
            return d(e4);
          }
          return be(t2);
        }, return(r4) {
          let o3;
          try {
            const t2 = he(e3.iterator, "return");
            if (void 0 === t2) return c({ done: true, value: r4 });
            o3 = S(t2, e3.iterator, [r4]);
          } catch (e4) {
            return d(e4);
          }
          return t(o3) ? be(o3) : d(new TypeError("The iterator.return() method must return an object"));
        } };
        return { iterator: r3, nextMethod: r3.next, done: false };
      })(me(e2, "sync", he(e2, Symbol.iterator)));
    }
  } else o2 = he(e2, Symbol.iterator);
  if (void 0 === o2) throw new TypeError("The object is not iterable");
  const n2 = S(o2, e2, []);
  if (!t(n2)) throw new TypeError("The iterator method must return an object");
  return { iterator: n2, nextMethod: n2.next, done: false };
}
function pe(e2) {
  const r2 = S(e2.nextMethod, e2.iterator, []);
  if (!t(r2)) throw new TypeError("The iterator.next() method must return an object");
  return r2;
}
var ye = class {
  constructor(e2, t2) {
    this._ongoingPromise = void 0, this._isFinished = false, this._reader = e2, this._preventCancel = t2;
  }
  next() {
    const e2 = () => this._nextSteps();
    return this._ongoingPromise = this._ongoingPromise ? m(this._ongoingPromise, e2, e2) : e2(), this._ongoingPromise;
  }
  return(e2) {
    const t2 = () => this._returnSteps(e2);
    return this._ongoingPromise = this._ongoingPromise ? m(this._ongoingPromise, t2, t2) : t2(), this._ongoingPromise;
  }
  _nextSteps() {
    if (this._isFinished) return Promise.resolve({ value: void 0, done: true });
    const e2 = this._reader, t2 = new Se(this);
    return te(e2, t2), t2._promise;
  }
  _returnSteps(e2) {
    if (this._isFinished) return Promise.resolve({ value: e2, done: true });
    this._isFinished = true;
    const t2 = this._reader;
    if (!this._preventCancel) {
      const r2 = W(t2, e2);
      return O(t2), m(r2, () => ({ value: e2, done: true }));
    }
    return O(t2), c({ value: e2, done: true });
  }
};
var Se = class {
  constructor(e2) {
    this._iterator = e2, this._promise = u((e3, t2) => {
      this._resolvePromise = e3, this._rejectPromise = t2;
    });
  }
  _chunkSteps(e2) {
    this._iterator._ongoingPromise = void 0, y(() => this._resolvePromise({ value: e2, done: false }));
  }
  _closeSteps() {
    const e2 = this._iterator;
    e2._ongoingPromise = void 0, e2._isFinished = true, O(e2._reader), this._resolvePromise({ value: void 0, done: true });
  }
  _errorSteps(e2) {
    const t2 = this._iterator;
    t2._ongoingPromise = void 0, t2._isFinished = true, O(t2._reader), this._rejectPromise(e2);
  }
};
var ge = { next() {
  return ve(this) ? this._asyncIteratorImpl.next() : d(we("next"));
}, return(e2) {
  return ve(this) ? this._asyncIteratorImpl.return(e2) : d(we("return"));
}, [_e]() {
  return this;
} };
function ve(e2) {
  if (!t(e2)) return false;
  if (!Object.prototype.hasOwnProperty.call(e2, "_asyncIteratorImpl")) return false;
  try {
    return e2._asyncIteratorImpl instanceof ye;
  } catch (e3) {
    return false;
  }
}
function we(e2) {
  return new TypeError(`ReadableStreamAsyncIterator.${e2} can only be used on a ReadableSteamAsyncIterator`);
}
Object.defineProperty(ge, _e, { enumerable: false });
var Re = Number.isNaN || function(e2) {
  return e2 != e2;
};
function Te(e2) {
  const t2 = fe(e2.buffer, e2.byteOffset, e2.byteOffset + e2.byteLength);
  return new Uint8Array(t2);
}
function Pe(e2) {
  const t2 = e2._queue.shift();
  return e2._queueTotalSize -= t2.size, e2._queueTotalSize < 0 && (e2._queueTotalSize = 0), t2.value;
}
function Ce(e2, t2, r2) {
  if ("number" != typeof (o2 = r2) || Re(o2) || o2 < 0 || r2 === 1 / 0) throw new RangeError("Size must be a finite, non-NaN, non-negative number.");
  var o2;
  e2._queue.push({ value: t2, size: r2 }), e2._queueTotalSize += r2;
}
function qe(e2) {
  e2._queue = new v(), e2._queueTotalSize = 0;
}
function Ee(e2) {
  return e2 === DataView;
}
function We(e2) {
  return Ee(e2) ? 1 : e2.BYTES_PER_ELEMENT;
}
var ReadableStreamBYOBRequest = class {
  constructor() {
    throw new TypeError("Illegal constructor");
  }
  get view() {
    if (!Be(this)) throw ot("view");
    return this._view;
  }
  respond(e2) {
    if (!Be(this)) throw ot("respond");
    if (M(e2, 1, "respond"), e2 = N(e2, "First parameter"), void 0 === this._associatedReadableByteStreamController) throw new TypeError("This BYOB request has been invalidated");
    if (de(this._view.buffer)) throw new TypeError("The BYOB request's buffer has been detached and so cannot be used as a response");
    et(this._associatedReadableByteStreamController, e2);
  }
  respondWithNewView(e2) {
    if (!Be(this)) throw ot("respondWithNewView");
    if (M(e2, 1, "respondWithNewView"), !ArrayBuffer.isView(e2)) throw new TypeError("You can only respond with array buffer views");
    if (void 0 === this._associatedReadableByteStreamController) throw new TypeError("This BYOB request has been invalidated");
    if (de(e2.buffer)) throw new TypeError("The given view's buffer has been detached and so cannot be used as a response");
    tt(this._associatedReadableByteStreamController, e2);
  }
};
Object.defineProperties(ReadableStreamBYOBRequest.prototype, { respond: { enumerable: true }, respondWithNewView: { enumerable: true }, view: { enumerable: true } }), o(ReadableStreamBYOBRequest.prototype.respond, "respond"), o(ReadableStreamBYOBRequest.prototype.respondWithNewView, "respondWithNewView"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableStreamBYOBRequest.prototype, Symbol.toStringTag, { value: "ReadableStreamBYOBRequest", configurable: true });
var ReadableByteStreamController = class {
  constructor() {
    throw new TypeError("Illegal constructor");
  }
  get byobRequest() {
    if (!Oe(this)) throw nt("byobRequest");
    return Ke(this);
  }
  get desiredSize() {
    if (!Oe(this)) throw nt("desiredSize");
    return Ze(this);
  }
  close() {
    if (!Oe(this)) throw nt("close");
    if (this._closeRequested) throw new TypeError("The stream has already been closed; do not close it again!");
    const e2 = this._controlledReadableByteStream._state;
    if ("readable" !== e2) throw new TypeError(`The stream (in ${e2} state) is not in the readable state and cannot be closed`);
    Ue(this);
  }
  enqueue(e2) {
    if (!Oe(this)) throw nt("enqueue");
    if (M(e2, 1, "enqueue"), !ArrayBuffer.isView(e2)) throw new TypeError("chunk must be an array buffer view");
    if (0 === e2.byteLength) throw new TypeError("chunk must have non-zero byteLength");
    if (0 === e2.buffer.byteLength) throw new TypeError("chunk's buffer must have non-zero byteLength");
    if (this._closeRequested) throw new TypeError("stream is closed or draining");
    const t2 = this._controlledReadableByteStream._state;
    if ("readable" !== t2) throw new TypeError(`The stream (in ${t2} state) is not in the readable state and cannot be enqueued to`);
    Ge(this, e2);
  }
  error(e2 = void 0) {
    if (!Oe(this)) throw nt("error");
    Xe(this, e2);
  }
  [T](e2) {
    ke(this), qe(this);
    const t2 = this._cancelAlgorithm(e2);
    return Ve(this), t2;
  }
  [P](e2) {
    const t2 = this._controlledReadableByteStream;
    if (this._queueTotalSize > 0) return void Je(this, e2);
    const r2 = this._autoAllocateChunkSize;
    if (void 0 !== r2) {
      let t3;
      try {
        t3 = new ArrayBuffer(r2);
      } catch (t4) {
        return void e2._errorSteps(t4);
      }
      const o2 = { buffer: t3, bufferByteLength: r2, byteOffset: 0, byteLength: r2, bytesFilled: 0, minimumFill: 1, elementSize: 1, viewConstructor: Uint8Array, readerType: "default" };
      this._pendingPullIntos.push(o2);
    }
    U(t2, e2), je(this);
  }
  [C]() {
    return this._queueTotalSize > 0;
  }
  [q]() {
    if (this._pendingPullIntos.length > 0) {
      const e2 = this._pendingPullIntos.peek();
      e2.readerType = "none", this._pendingPullIntos = new v(), this._pendingPullIntos.push(e2);
    }
  }
};
function Oe(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_controlledReadableByteStream") && e2 instanceof ReadableByteStreamController);
}
function Be(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_associatedReadableByteStreamController") && e2 instanceof ReadableStreamBYOBRequest);
}
function je(e2) {
  const t2 = (function(e3) {
    const t3 = e3._controlledReadableByteStream;
    if ("readable" !== t3._state) return false;
    if (e3._closeRequested) return false;
    if (!e3._started) return false;
    if (J(t3) && X(t3) > 0) return true;
    if (ut(t3) && lt(t3) > 0) return true;
    const r2 = Ze(e3);
    if (r2 > 0) return true;
    return false;
  })(e2);
  if (!t2) return;
  if (e2._pulling) return void (e2._pullAgain = true);
  e2._pulling = true;
  h(e2._pullAlgorithm(), () => (e2._pulling = false, e2._pullAgain && (e2._pullAgain = false, je(e2)), null), (t3) => (Xe(e2, t3), null));
}
function ke(e2) {
  xe(e2), e2._pendingPullIntos = new v();
}
function Ae(e2, t2) {
  let r2 = false;
  "closed" === e2._state && (r2 = true);
  const o2 = De(t2);
  "default" === t2.readerType ? G(e2, o2, r2) : (function(e3, t3, r3) {
    const o3 = e3._reader, n2 = o3._readIntoRequests.shift();
    r3 ? n2._closeSteps(t3) : n2._chunkSteps(t3);
  })(e2, o2, r2);
}
function ze(e2, t2) {
  for (let r2 = 0; r2 < t2.length; ++r2) Ae(e2, t2[r2]);
}
function De(e2) {
  const t2 = e2.bytesFilled, r2 = e2.elementSize;
  return new e2.viewConstructor(e2.buffer, e2.byteOffset, t2 / r2);
}
function Fe(e2, t2, r2, o2) {
  e2._queue.push({ buffer: t2, byteOffset: r2, byteLength: o2 }), e2._queueTotalSize += o2;
}
function Le(e2, t2, r2, o2) {
  let n2;
  try {
    n2 = fe(t2, r2, r2 + o2);
  } catch (t3) {
    throw Xe(e2, t3), t3;
  }
  Fe(e2, n2, 0, o2);
}
function Ie(e2, t2) {
  t2.bytesFilled > 0 && Le(e2, t2.buffer, t2.byteOffset, t2.bytesFilled), He(e2);
}
function $e(e2, t2) {
  const r2 = Math.min(e2._queueTotalSize, t2.byteLength - t2.bytesFilled), o2 = t2.bytesFilled + r2;
  let n2 = r2, i2 = false;
  const a2 = o2 - o2 % t2.elementSize;
  a2 >= t2.minimumFill && (n2 = a2 - t2.bytesFilled, i2 = true);
  const s2 = e2._queue;
  for (; n2 > 0; ) {
    const r3 = s2.peek(), o3 = Math.min(n2, r3.byteLength), i3 = t2.byteOffset + t2.bytesFilled;
    ue(t2.buffer, i3, r3.buffer, r3.byteOffset, o3), r3.byteLength === o3 ? s2.shift() : (r3.byteOffset += o3, r3.byteLength -= o3), e2._queueTotalSize -= o3, Me(e2, o3, t2), n2 -= o3;
  }
  return i2;
}
function Me(e2, t2, r2) {
  r2.bytesFilled += t2;
}
function Ye(e2) {
  0 === e2._queueTotalSize && e2._closeRequested ? (Ve(e2), Yr(e2._controlledReadableByteStream)) : je(e2);
}
function xe(e2) {
  null !== e2._byobRequest && (e2._byobRequest._associatedReadableByteStreamController = void 0, e2._byobRequest._view = null, e2._byobRequest = null);
}
function Qe(e2) {
  const t2 = [];
  for (; e2._pendingPullIntos.length > 0 && 0 !== e2._queueTotalSize; ) {
    const r2 = e2._pendingPullIntos.peek();
    $e(e2, r2) && (He(e2), t2.push(r2));
  }
  return t2;
}
function Ne(e2, t2) {
  const r2 = e2._pendingPullIntos.peek();
  xe(e2);
  "closed" === e2._controlledReadableByteStream._state ? (function(e3, t3) {
    "none" === t3.readerType && He(e3);
    const r3 = e3._controlledReadableByteStream;
    if (ut(r3)) {
      const t4 = [];
      for (; t4.length < lt(r3); ) t4.push(He(e3));
      ze(r3, t4);
    }
  })(e2, r2) : (function(e3, t3, r3) {
    if (Me(0, t3, r3), "none" === r3.readerType) {
      Ie(e3, r3);
      const t4 = Qe(e3);
      return void ze(e3._controlledReadableByteStream, t4);
    }
    if (r3.bytesFilled < r3.minimumFill) return;
    He(e3);
    const o2 = r3.bytesFilled % r3.elementSize;
    if (o2 > 0) {
      const t4 = r3.byteOffset + r3.bytesFilled;
      Le(e3, r3.buffer, t4 - o2, o2);
    }
    r3.bytesFilled -= o2;
    const n2 = Qe(e3);
    Ae(e3._controlledReadableByteStream, r3), ze(e3._controlledReadableByteStream, n2);
  })(e2, t2, r2), je(e2);
}
function He(e2) {
  return e2._pendingPullIntos.shift();
}
function Ve(e2) {
  e2._pullAlgorithm = void 0, e2._cancelAlgorithm = void 0;
}
function Ue(e2) {
  const t2 = e2._controlledReadableByteStream;
  if (!e2._closeRequested && "readable" === t2._state) if (e2._queueTotalSize > 0) e2._closeRequested = true;
  else {
    if (e2._pendingPullIntos.length > 0) {
      const t3 = e2._pendingPullIntos.peek();
      if (t3.bytesFilled % t3.elementSize !== 0) {
        const t4 = new TypeError("Insufficient bytes to fill elements in the given buffer");
        throw Xe(e2, t4), t4;
      }
    }
    Ve(e2), Yr(t2);
  }
}
function Ge(e2, t2) {
  const r2 = e2._controlledReadableByteStream;
  if (e2._closeRequested || "readable" !== r2._state) return;
  const { buffer: o2, byteOffset: n2, byteLength: i2 } = t2;
  if (de(o2)) throw new TypeError("chunk's buffer is detached and so cannot be enqueued");
  const a2 = ce(o2);
  if (e2._pendingPullIntos.length > 0) {
    const t3 = e2._pendingPullIntos.peek();
    if (de(t3.buffer)) throw new TypeError("The BYOB request's buffer has been detached and so cannot be filled with an enqueued chunk");
    xe(e2), t3.buffer = ce(t3.buffer), "none" === t3.readerType && Ie(e2, t3);
  }
  if (J(r2)) if ((function(e3) {
    const t3 = e3._controlledReadableByteStream._reader;
    for (; t3._readRequests.length > 0; ) {
      if (0 === e3._queueTotalSize) return;
      Je(e3, t3._readRequests.shift());
    }
  })(e2), 0 === X(r2)) Fe(e2, a2, n2, i2);
  else {
    e2._pendingPullIntos.length > 0 && He(e2);
    G(r2, new Uint8Array(a2, n2, i2), false);
  }
  else if (ut(r2)) {
    Fe(e2, a2, n2, i2);
    ze(r2, Qe(e2));
  } else Fe(e2, a2, n2, i2);
  je(e2);
}
function Xe(e2, t2) {
  const r2 = e2._controlledReadableByteStream;
  "readable" === r2._state && (ke(e2), qe(e2), Ve(e2), xr(r2, t2));
}
function Je(e2, t2) {
  const r2 = e2._queue.shift();
  e2._queueTotalSize -= r2.byteLength, Ye(e2);
  const o2 = new Uint8Array(r2.buffer, r2.byteOffset, r2.byteLength);
  t2._chunkSteps(o2);
}
function Ke(e2) {
  if (null === e2._byobRequest && e2._pendingPullIntos.length > 0) {
    const t2 = e2._pendingPullIntos.peek(), r2 = new Uint8Array(t2.buffer, t2.byteOffset + t2.bytesFilled, t2.byteLength - t2.bytesFilled), o2 = Object.create(ReadableStreamBYOBRequest.prototype);
    !(function(e3, t3, r3) {
      e3._associatedReadableByteStreamController = t3, e3._view = r3;
    })(o2, e2, r2), e2._byobRequest = o2;
  }
  return e2._byobRequest;
}
function Ze(e2) {
  const t2 = e2._controlledReadableByteStream._state;
  return "errored" === t2 ? null : "closed" === t2 ? 0 : e2._strategyHWM - e2._queueTotalSize;
}
function et(e2, t2) {
  const r2 = e2._pendingPullIntos.peek();
  if ("closed" === e2._controlledReadableByteStream._state) {
    if (0 !== t2) throw new TypeError("bytesWritten must be 0 when calling respond() on a closed stream");
  } else {
    if (0 === t2) throw new TypeError("bytesWritten must be greater than 0 when calling respond() on a readable stream");
    if (r2.bytesFilled + t2 > r2.byteLength) throw new RangeError("bytesWritten out of range");
  }
  r2.buffer = ce(r2.buffer), Ne(e2, t2);
}
function tt(e2, t2) {
  const r2 = e2._pendingPullIntos.peek();
  if ("closed" === e2._controlledReadableByteStream._state) {
    if (0 !== t2.byteLength) throw new TypeError("The view's length must be 0 when calling respondWithNewView() on a closed stream");
  } else if (0 === t2.byteLength) throw new TypeError("The view's length must be greater than 0 when calling respondWithNewView() on a readable stream");
  if (r2.byteOffset + r2.bytesFilled !== t2.byteOffset) throw new RangeError("The region specified by view does not match byobRequest");
  if (r2.bufferByteLength !== t2.buffer.byteLength) throw new RangeError("The buffer of view has different capacity than byobRequest");
  if (r2.bytesFilled + t2.byteLength > r2.byteLength) throw new RangeError("The region specified by view is larger than byobRequest");
  const o2 = t2.byteLength;
  r2.buffer = ce(t2.buffer), Ne(e2, o2);
}
function rt(e2, t2, r2, o2, n2, i2, a2) {
  t2._controlledReadableByteStream = e2, t2._pullAgain = false, t2._pulling = false, t2._byobRequest = null, t2._queue = t2._queueTotalSize = void 0, qe(t2), t2._closeRequested = false, t2._started = false, t2._strategyHWM = i2, t2._pullAlgorithm = o2, t2._cancelAlgorithm = n2, t2._autoAllocateChunkSize = a2, t2._pendingPullIntos = new v(), e2._readableStreamController = t2;
  h(c(r2()), () => (t2._started = true, je(t2), null), (e3) => (Xe(t2, e3), null));
}
function ot(e2) {
  return new TypeError(`ReadableStreamBYOBRequest.prototype.${e2} can only be used on a ReadableStreamBYOBRequest`);
}
function nt(e2) {
  return new TypeError(`ReadableByteStreamController.prototype.${e2} can only be used on a ReadableByteStreamController`);
}
function it(e2, t2) {
  if ("byob" !== (e2 = `${e2}`)) throw new TypeError(`${t2} '${e2}' is not a valid enumeration value for ReadableStreamReaderMode`);
  return e2;
}
function at(e2) {
  return new ReadableStreamBYOBReader(e2);
}
function st(e2, t2) {
  e2._reader._readIntoRequests.push(t2);
}
function lt(e2) {
  return e2._reader._readIntoRequests.length;
}
function ut(e2) {
  const t2 = e2._reader;
  return void 0 !== t2 && !!ft(t2);
}
Object.defineProperties(ReadableByteStreamController.prototype, { close: { enumerable: true }, enqueue: { enumerable: true }, error: { enumerable: true }, byobRequest: { enumerable: true }, desiredSize: { enumerable: true } }), o(ReadableByteStreamController.prototype.close, "close"), o(ReadableByteStreamController.prototype.enqueue, "enqueue"), o(ReadableByteStreamController.prototype.error, "error"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableByteStreamController.prototype, Symbol.toStringTag, { value: "ReadableByteStreamController", configurable: true });
var ReadableStreamBYOBReader = class {
  constructor(e2) {
    if (M(e2, 1, "ReadableStreamBYOBReader"), H(e2, "First parameter"), $r(e2)) throw new TypeError("This stream has already been locked for exclusive reading by another reader");
    if (!Oe(e2._readableStreamController)) throw new TypeError("Cannot construct a ReadableStreamBYOBReader for a stream not constructed with a byte source");
    E(this, e2), this._readIntoRequests = new v();
  }
  get closed() {
    return ft(this) ? this._closedPromise : d(_t("closed"));
  }
  cancel(e2 = void 0) {
    return ft(this) ? void 0 === this._ownerReadableStream ? d(B("cancel")) : W(this, e2) : d(_t("cancel"));
  }
  read(e2, t2 = {}) {
    if (!ft(this)) return d(_t("read"));
    if (!ArrayBuffer.isView(e2)) return d(new TypeError("view must be an array buffer view"));
    if (0 === e2.byteLength) return d(new TypeError("view must have non-zero byteLength"));
    if (0 === e2.buffer.byteLength) return d(new TypeError("view's buffer must have non-zero byteLength"));
    if (de(e2.buffer)) return d(new TypeError("view's buffer has been detached"));
    let r2;
    try {
      r2 = (function(e3, t3) {
        var r3;
        return L(e3, t3), { min: N(null !== (r3 = null == e3 ? void 0 : e3.min) && void 0 !== r3 ? r3 : 1, `${t3} has member 'min' that`) };
      })(t2, "options");
    } catch (e3) {
      return d(e3);
    }
    const o2 = r2.min;
    if (0 === o2) return d(new TypeError("options.min must be greater than 0"));
    if ((function(e3) {
      return Ee(e3.constructor);
    })(e2)) {
      if (o2 > e2.byteLength) return d(new RangeError("options.min must be less than or equal to view's byteLength"));
    } else if (o2 > e2.length) return d(new RangeError("options.min must be less than or equal to view's length"));
    if (void 0 === this._ownerReadableStream) return d(B("read from"));
    const n2 = (function(e3, t3, r3) {
      const o3 = e3._ownerReadableStream;
      return "errored" === o3._state || (function(e4, t4, r4) {
        const o4 = e4._controlledReadableByteStream, n3 = We(t4.constructor), { byteLength: i2 } = t4, a2 = r4 * n3;
        return !(e4._pendingPullIntos.length > 0) && ("closed" === o4._state || e4._queueTotalSize >= a2);
      })(o3._readableStreamController, t3, r3);
    })(this, e2, o2) ? new dt() : new ct();
    return ht(this, e2, o2, n2), n2._promise;
  }
  releaseLock() {
    if (!ft(this)) throw _t("releaseLock");
    void 0 !== this._ownerReadableStream && (function(e2) {
      O(e2);
      const t2 = new TypeError("Reader was released");
      bt(e2, t2);
    })(this);
  }
};
Object.defineProperties(ReadableStreamBYOBReader.prototype, { cancel: { enumerable: true }, read: { enumerable: true }, releaseLock: { enumerable: true }, closed: { enumerable: true } }), o(ReadableStreamBYOBReader.prototype.cancel, "cancel"), o(ReadableStreamBYOBReader.prototype.read, "read"), o(ReadableStreamBYOBReader.prototype.releaseLock, "releaseLock"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableStreamBYOBReader.prototype, Symbol.toStringTag, { value: "ReadableStreamBYOBReader", configurable: true });
var ct = class {
  constructor() {
    this._promise = u((e2, t2) => {
      this._resolvePromise = e2, this._rejectPromise = t2;
    });
  }
  _chunkSteps(e2) {
    this._resolvePromise({ value: e2, done: false });
  }
  _closeSteps(e2) {
    this._resolvePromise({ value: e2, done: true });
  }
  _errorSteps(e2) {
    this._rejectPromise(e2);
  }
};
var dt = class {
  constructor() {
    this._promise = void 0;
  }
  _chunkSteps(e2) {
    this._promise = l({ value: e2, done: false });
  }
  _closeSteps(e2) {
    this._promise = l({ value: e2, done: true });
  }
  _errorSteps(e2) {
    this._promise = d(e2);
  }
};
function ft(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_readIntoRequests") && e2 instanceof ReadableStreamBYOBReader);
}
function ht(e2, t2, r2, o2) {
  const n2 = e2._ownerReadableStream;
  n2._disturbed = true, "errored" === n2._state ? o2._errorSteps(n2._storedError) : (function(e3, t3, r3, o3) {
    const n3 = e3._controlledReadableByteStream, i2 = t3.constructor, a2 = We(i2), { byteOffset: s2, byteLength: l2 } = t3, u2 = r3 * a2;
    let c2;
    try {
      c2 = ce(t3.buffer);
    } catch (e4) {
      return void o3._errorSteps(e4);
    }
    const d2 = { buffer: c2, bufferByteLength: c2.byteLength, byteOffset: s2, byteLength: l2, bytesFilled: 0, minimumFill: u2, elementSize: a2, viewConstructor: i2, readerType: "byob" };
    if (e3._pendingPullIntos.length > 0) return e3._pendingPullIntos.push(d2), void st(n3, o3);
    if ("closed" === n3._state) {
      const e4 = new i2(d2.buffer, d2.byteOffset, 0);
      return void o3._closeSteps(e4);
    }
    if (e3._queueTotalSize > 0) {
      if ($e(e3, d2)) {
        const t4 = De(d2);
        return Ye(e3), void o3._chunkSteps(t4);
      }
      if (e3._closeRequested) {
        const t4 = new TypeError("Insufficient bytes to fill elements in the given buffer");
        return Xe(e3, t4), void o3._errorSteps(t4);
      }
    }
    e3._pendingPullIntos.push(d2), st(n3, o3), je(e3);
  })(n2._readableStreamController, t2, r2, o2);
}
function bt(e2, t2) {
  const r2 = e2._readIntoRequests;
  e2._readIntoRequests = new v(), r2.forEach((e3) => {
    e3._errorSteps(t2);
  });
}
function _t(e2) {
  return new TypeError(`ReadableStreamBYOBReader.prototype.${e2} can only be used on a ReadableStreamBYOBReader`);
}
function mt(e2, t2) {
  const { highWaterMark: r2 } = e2;
  if (void 0 === r2) return t2;
  if (Re(r2) || r2 < 0) throw new RangeError("Invalid highWaterMark");
  return r2;
}
function pt(e2) {
  const { size: t2 } = e2;
  return t2 || (() => 1);
}
function yt(e2, t2) {
  L(e2, t2);
  const r2 = null == e2 ? void 0 : e2.highWaterMark, o2 = null == e2 ? void 0 : e2.size;
  return { highWaterMark: void 0 === r2 ? void 0 : x(r2), size: void 0 === o2 ? void 0 : St(o2, `${t2} has member 'size' that`) };
}
function St(e2, t2) {
  return I(e2, t2), (t3) => x(e2(t3));
}
function gt(e2, t2, r2) {
  return I(e2, r2), (r3) => g(e2, t2, [r3]);
}
function vt(e2, t2, r2) {
  return I(e2, r2), () => g(e2, t2, []);
}
function wt(e2, t2, r2) {
  return I(e2, r2), (r3) => S(e2, t2, [r3]);
}
function Rt(e2, t2, r2) {
  return I(e2, r2), (r3, o2) => g(e2, t2, [r3, o2]);
}
function Tt(e2, t2) {
  if (!qt(e2)) throw new TypeError(`${t2} is not a WritableStream.`);
}
var WritableStream2 = class {
  constructor(e2 = {}, t2 = {}) {
    void 0 === e2 ? e2 = null : $(e2, "First parameter");
    const r2 = yt(t2, "Second parameter"), o2 = (function(e3, t3) {
      L(e3, t3);
      const r3 = null == e3 ? void 0 : e3.abort, o3 = null == e3 ? void 0 : e3.close, n3 = null == e3 ? void 0 : e3.start, i2 = null == e3 ? void 0 : e3.type, a2 = null == e3 ? void 0 : e3.write;
      return { abort: void 0 === r3 ? void 0 : gt(r3, e3, `${t3} has member 'abort' that`), close: void 0 === o3 ? void 0 : vt(o3, e3, `${t3} has member 'close' that`), start: void 0 === n3 ? void 0 : wt(n3, e3, `${t3} has member 'start' that`), write: void 0 === a2 ? void 0 : Rt(a2, e3, `${t3} has member 'write' that`), type: i2 };
    })(e2, "First parameter");
    Ct(this);
    if (void 0 !== o2.type) throw new RangeError("Invalid type is specified");
    const n2 = pt(r2);
    !(function(e3, t3, r3, o3) {
      const n3 = Object.create(WritableStreamDefaultController.prototype);
      let i2, a2, s2, l2;
      i2 = void 0 !== t3.start ? () => t3.start(n3) : () => {
      };
      a2 = void 0 !== t3.write ? (e4) => t3.write(e4, n3) : () => c(void 0);
      s2 = void 0 !== t3.close ? () => t3.close() : () => c(void 0);
      l2 = void 0 !== t3.abort ? (e4) => t3.abort(e4) : () => c(void 0);
      Nt(e3, n3, i2, a2, s2, l2, r3, o3);
    })(this, o2, mt(r2, 1), n2);
  }
  get locked() {
    if (!qt(this)) throw Kt("locked");
    return Et(this);
  }
  abort(e2 = void 0) {
    return qt(this) ? Et(this) ? d(new TypeError("Cannot abort a stream that already has a writer")) : Wt(this, e2) : d(Kt("abort"));
  }
  close() {
    return qt(this) ? Et(this) ? d(new TypeError("Cannot close a stream that already has a writer")) : At(this) ? d(new TypeError("Cannot close an already-closing stream")) : Ot(this) : d(Kt("close"));
  }
  getWriter() {
    if (!qt(this)) throw Kt("getWriter");
    return Pt(this);
  }
};
function Pt(e2) {
  return new WritableStreamDefaultWriter(e2);
}
function Ct(e2) {
  e2._state = "writable", e2._storedError = void 0, e2._writer = void 0, e2._writableStreamController = void 0, e2._writeRequests = new v(), e2._inFlightWriteRequest = void 0, e2._closeRequest = void 0, e2._inFlightCloseRequest = void 0, e2._pendingAbortRequest = void 0, e2._backpressure = false;
}
function qt(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_writableStreamController") && e2 instanceof WritableStream2);
}
function Et(e2) {
  return void 0 !== e2._writer;
}
function Wt(e2, t2) {
  var r2;
  if ("closed" === e2._state || "errored" === e2._state) return c(void 0);
  e2._writableStreamController._abortReason = t2, null === (r2 = e2._writableStreamController._abortController) || void 0 === r2 || r2.abort(t2);
  const o2 = e2._state;
  if ("closed" === o2 || "errored" === o2) return c(void 0);
  if (void 0 !== e2._pendingAbortRequest) return e2._pendingAbortRequest._promise;
  let n2 = false;
  "erroring" === o2 && (n2 = true, t2 = void 0);
  const i2 = u((r3, o3) => {
    e2._pendingAbortRequest = { _promise: void 0, _resolve: r3, _reject: o3, _reason: t2, _wasAlreadyErroring: n2 };
  });
  return e2._pendingAbortRequest._promise = i2, n2 || jt(e2, t2), i2;
}
function Ot(e2) {
  const t2 = e2._state;
  if ("closed" === t2 || "errored" === t2) return d(new TypeError(`The stream (in ${t2} state) is not in the writable state and cannot be closed`));
  const r2 = u((t3, r3) => {
    const o3 = { _resolve: t3, _reject: r3 };
    e2._closeRequest = o3;
  }), o2 = e2._writer;
  var n2;
  return void 0 !== o2 && e2._backpressure && "writable" === t2 && cr(o2), Ce(n2 = e2._writableStreamController, xt, 0), Ut(n2), r2;
}
function Bt(e2, t2) {
  "writable" !== e2._state ? kt(e2) : jt(e2, t2);
}
function jt(e2, t2) {
  const r2 = e2._writableStreamController;
  e2._state = "erroring", e2._storedError = t2;
  const o2 = e2._writer;
  void 0 !== o2 && $t(o2, t2), !(function(e3) {
    if (void 0 === e3._inFlightWriteRequest && void 0 === e3._inFlightCloseRequest) return false;
    return true;
  })(e2) && r2._started && kt(e2);
}
function kt(e2) {
  e2._state = "errored", e2._writableStreamController[R]();
  const t2 = e2._storedError;
  if (e2._writeRequests.forEach((e3) => {
    e3._reject(t2);
  }), e2._writeRequests = new v(), void 0 === e2._pendingAbortRequest) return void zt(e2);
  const r2 = e2._pendingAbortRequest;
  if (e2._pendingAbortRequest = void 0, r2._wasAlreadyErroring) return r2._reject(t2), void zt(e2);
  h(e2._writableStreamController[w](r2._reason), () => (r2._resolve(), zt(e2), null), (t3) => (r2._reject(t3), zt(e2), null));
}
function At(e2) {
  return void 0 !== e2._closeRequest || void 0 !== e2._inFlightCloseRequest;
}
function zt(e2) {
  void 0 !== e2._closeRequest && (e2._closeRequest._reject(e2._storedError), e2._closeRequest = void 0);
  const t2 = e2._writer;
  void 0 !== t2 && nr(t2, e2._storedError);
}
function Dt(e2, t2) {
  const r2 = e2._writer;
  void 0 !== r2 && t2 !== e2._backpressure && (t2 ? (function(e3) {
    ar(e3);
  })(r2) : cr(r2)), e2._backpressure = t2;
}
Object.defineProperties(WritableStream2.prototype, { abort: { enumerable: true }, close: { enumerable: true }, getWriter: { enumerable: true }, locked: { enumerable: true } }), o(WritableStream2.prototype.abort, "abort"), o(WritableStream2.prototype.close, "close"), o(WritableStream2.prototype.getWriter, "getWriter"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(WritableStream2.prototype, Symbol.toStringTag, { value: "WritableStream", configurable: true });
var WritableStreamDefaultWriter = class {
  constructor(e2) {
    if (M(e2, 1, "WritableStreamDefaultWriter"), Tt(e2, "First parameter"), Et(e2)) throw new TypeError("This stream has already been locked for exclusive writing by another writer");
    this._ownerWritableStream = e2, e2._writer = this;
    const t2 = e2._state;
    if ("writable" === t2) !At(e2) && e2._backpressure ? ar(this) : lr(this), rr(this);
    else if ("erroring" === t2) sr(this, e2._storedError), rr(this);
    else if ("closed" === t2) lr(this), rr(r2 = this), ir(r2);
    else {
      const t3 = e2._storedError;
      sr(this, t3), or(this, t3);
    }
    var r2;
  }
  get closed() {
    return Ft(this) ? this._closedPromise : d(er("closed"));
  }
  get desiredSize() {
    if (!Ft(this)) throw er("desiredSize");
    if (void 0 === this._ownerWritableStream) throw tr("desiredSize");
    return (function(e2) {
      const t2 = e2._ownerWritableStream, r2 = t2._state;
      if ("errored" === r2 || "erroring" === r2) return null;
      if ("closed" === r2) return 0;
      return Vt(t2._writableStreamController);
    })(this);
  }
  get ready() {
    return Ft(this) ? this._readyPromise : d(er("ready"));
  }
  abort(e2 = void 0) {
    return Ft(this) ? void 0 === this._ownerWritableStream ? d(tr("abort")) : (function(e3, t2) {
      return Wt(e3._ownerWritableStream, t2);
    })(this, e2) : d(er("abort"));
  }
  close() {
    if (!Ft(this)) return d(er("close"));
    const e2 = this._ownerWritableStream;
    return void 0 === e2 ? d(tr("close")) : At(e2) ? d(new TypeError("Cannot close an already-closing stream")) : Lt(this);
  }
  releaseLock() {
    if (!Ft(this)) throw er("releaseLock");
    void 0 !== this._ownerWritableStream && Mt(this);
  }
  write(e2 = void 0) {
    return Ft(this) ? void 0 === this._ownerWritableStream ? d(tr("write to")) : Yt(this, e2) : d(er("write"));
  }
};
function Ft(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_ownerWritableStream") && e2 instanceof WritableStreamDefaultWriter);
}
function Lt(e2) {
  return Ot(e2._ownerWritableStream);
}
function It(e2, t2) {
  "pending" === e2._closedPromiseState ? nr(e2, t2) : (function(e3, t3) {
    or(e3, t3);
  })(e2, t2);
}
function $t(e2, t2) {
  "pending" === e2._readyPromiseState ? ur(e2, t2) : (function(e3, t3) {
    sr(e3, t3);
  })(e2, t2);
}
function Mt(e2) {
  const t2 = e2._ownerWritableStream, r2 = new TypeError("Writer was released and can no longer be used to monitor the stream's closedness");
  $t(e2, r2), It(e2, r2), t2._writer = void 0, e2._ownerWritableStream = void 0;
}
function Yt(e2, t2) {
  const r2 = e2._ownerWritableStream, o2 = r2._writableStreamController, n2 = (function(e3, t3) {
    if (void 0 === e3._strategySizeAlgorithm) return 1;
    try {
      return e3._strategySizeAlgorithm(t3);
    } catch (t4) {
      return Gt(e3, t4), 1;
    }
  })(o2, t2);
  if (r2 !== e2._ownerWritableStream) return d(tr("write to"));
  const i2 = r2._state;
  if ("errored" === i2) return d(r2._storedError);
  if (At(r2) || "closed" === i2) return d(new TypeError("The stream is closing or closed and cannot be written to"));
  if ("erroring" === i2) return d(r2._storedError);
  const a2 = (function(e3) {
    return u((t3, r3) => {
      const o3 = { _resolve: t3, _reject: r3 };
      e3._writeRequests.push(o3);
    });
  })(r2);
  return (function(e3, t3, r3) {
    try {
      Ce(e3, t3, r3);
    } catch (t4) {
      return void Gt(e3, t4);
    }
    const o3 = e3._controlledWritableStream;
    if (!At(o3) && "writable" === o3._state) {
      Dt(o3, Xt(e3));
    }
    Ut(e3);
  })(o2, t2, n2), a2;
}
Object.defineProperties(WritableStreamDefaultWriter.prototype, { abort: { enumerable: true }, close: { enumerable: true }, releaseLock: { enumerable: true }, write: { enumerable: true }, closed: { enumerable: true }, desiredSize: { enumerable: true }, ready: { enumerable: true } }), o(WritableStreamDefaultWriter.prototype.abort, "abort"), o(WritableStreamDefaultWriter.prototype.close, "close"), o(WritableStreamDefaultWriter.prototype.releaseLock, "releaseLock"), o(WritableStreamDefaultWriter.prototype.write, "write"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(WritableStreamDefaultWriter.prototype, Symbol.toStringTag, { value: "WritableStreamDefaultWriter", configurable: true });
var xt = {};
var WritableStreamDefaultController = class {
  constructor() {
    throw new TypeError("Illegal constructor");
  }
  get abortReason() {
    if (!Qt(this)) throw Zt("abortReason");
    return this._abortReason;
  }
  get signal() {
    if (!Qt(this)) throw Zt("signal");
    if (void 0 === this._abortController) throw new TypeError("WritableStreamDefaultController.prototype.signal is not supported");
    return this._abortController.signal;
  }
  error(e2 = void 0) {
    if (!Qt(this)) throw Zt("error");
    "writable" === this._controlledWritableStream._state && Jt(this, e2);
  }
  [w](e2) {
    const t2 = this._abortAlgorithm(e2);
    return Ht(this), t2;
  }
  [R]() {
    qe(this);
  }
};
function Qt(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_controlledWritableStream") && e2 instanceof WritableStreamDefaultController);
}
function Nt(e2, t2, r2, o2, n2, i2, a2, s2) {
  t2._controlledWritableStream = e2, e2._writableStreamController = t2, t2._queue = void 0, t2._queueTotalSize = void 0, qe(t2), t2._abortReason = void 0, t2._abortController = (function() {
    if ("function" == typeof AbortController) return new AbortController();
  })(), t2._started = false, t2._strategySizeAlgorithm = s2, t2._strategyHWM = a2, t2._writeAlgorithm = o2, t2._closeAlgorithm = n2, t2._abortAlgorithm = i2;
  const l2 = Xt(t2);
  Dt(e2, l2);
  h(c(r2()), () => (t2._started = true, Ut(t2), null), (r3) => (t2._started = true, Bt(e2, r3), null));
}
function Ht(e2) {
  e2._writeAlgorithm = void 0, e2._closeAlgorithm = void 0, e2._abortAlgorithm = void 0, e2._strategySizeAlgorithm = void 0;
}
function Vt(e2) {
  return e2._strategyHWM - e2._queueTotalSize;
}
function Ut(e2) {
  const t2 = e2._controlledWritableStream;
  if (!e2._started) return;
  if (void 0 !== t2._inFlightWriteRequest) return;
  if ("erroring" === t2._state) return void kt(t2);
  if (0 === e2._queue.length) return;
  const r2 = e2._queue.peek().value;
  r2 === xt ? (function(e3) {
    const t3 = e3._controlledWritableStream;
    (function(e4) {
      e4._inFlightCloseRequest = e4._closeRequest, e4._closeRequest = void 0;
    })(t3), Pe(e3);
    const r3 = e3._closeAlgorithm();
    Ht(e3), h(r3, () => ((function(e4) {
      e4._inFlightCloseRequest._resolve(void 0), e4._inFlightCloseRequest = void 0, "erroring" === e4._state && (e4._storedError = void 0, void 0 !== e4._pendingAbortRequest && (e4._pendingAbortRequest._resolve(), e4._pendingAbortRequest = void 0)), e4._state = "closed";
      const t4 = e4._writer;
      void 0 !== t4 && ir(t4);
    })(t3), null), (e4) => ((function(e5, t4) {
      e5._inFlightCloseRequest._reject(t4), e5._inFlightCloseRequest = void 0, void 0 !== e5._pendingAbortRequest && (e5._pendingAbortRequest._reject(t4), e5._pendingAbortRequest = void 0), Bt(e5, t4);
    })(t3, e4), null));
  })(e2) : (function(e3, t3) {
    const r3 = e3._controlledWritableStream;
    !(function(e4) {
      e4._inFlightWriteRequest = e4._writeRequests.shift();
    })(r3);
    const o2 = e3._writeAlgorithm(t3);
    h(o2, () => {
      !(function(e4) {
        e4._inFlightWriteRequest._resolve(void 0), e4._inFlightWriteRequest = void 0;
      })(r3);
      const t4 = r3._state;
      if (Pe(e3), !At(r3) && "writable" === t4) {
        const t5 = Xt(e3);
        Dt(r3, t5);
      }
      return Ut(e3), null;
    }, (t4) => ("writable" === r3._state && Ht(e3), (function(e4, t5) {
      e4._inFlightWriteRequest._reject(t5), e4._inFlightWriteRequest = void 0, Bt(e4, t5);
    })(r3, t4), null));
  })(e2, r2);
}
function Gt(e2, t2) {
  "writable" === e2._controlledWritableStream._state && Jt(e2, t2);
}
function Xt(e2) {
  return Vt(e2) <= 0;
}
function Jt(e2, t2) {
  const r2 = e2._controlledWritableStream;
  Ht(e2), jt(r2, t2);
}
function Kt(e2) {
  return new TypeError(`WritableStream.prototype.${e2} can only be used on a WritableStream`);
}
function Zt(e2) {
  return new TypeError(`WritableStreamDefaultController.prototype.${e2} can only be used on a WritableStreamDefaultController`);
}
function er(e2) {
  return new TypeError(`WritableStreamDefaultWriter.prototype.${e2} can only be used on a WritableStreamDefaultWriter`);
}
function tr(e2) {
  return new TypeError("Cannot " + e2 + " a stream using a released writer");
}
function rr(e2) {
  e2._closedPromise = u((t2, r2) => {
    e2._closedPromise_resolve = t2, e2._closedPromise_reject = r2, e2._closedPromiseState = "pending";
  });
}
function or(e2, t2) {
  rr(e2), nr(e2, t2);
}
function nr(e2, t2) {
  void 0 !== e2._closedPromise_reject && (p(e2._closedPromise), e2._closedPromise_reject(t2), e2._closedPromise_resolve = void 0, e2._closedPromise_reject = void 0, e2._closedPromiseState = "rejected");
}
function ir(e2) {
  void 0 !== e2._closedPromise_resolve && (e2._closedPromise_resolve(void 0), e2._closedPromise_resolve = void 0, e2._closedPromise_reject = void 0, e2._closedPromiseState = "resolved");
}
function ar(e2) {
  e2._readyPromise = u((t2, r2) => {
    e2._readyPromise_resolve = t2, e2._readyPromise_reject = r2;
  }), e2._readyPromiseState = "pending";
}
function sr(e2, t2) {
  ar(e2), ur(e2, t2);
}
function lr(e2) {
  ar(e2), cr(e2);
}
function ur(e2, t2) {
  void 0 !== e2._readyPromise_reject && (p(e2._readyPromise), e2._readyPromise_reject(t2), e2._readyPromise_resolve = void 0, e2._readyPromise_reject = void 0, e2._readyPromiseState = "rejected");
}
function cr(e2) {
  void 0 !== e2._readyPromise_resolve && (e2._readyPromise_resolve(void 0), e2._readyPromise_resolve = void 0, e2._readyPromise_reject = void 0, e2._readyPromiseState = "fulfilled");
}
Object.defineProperties(WritableStreamDefaultController.prototype, { abortReason: { enumerable: true }, signal: { enumerable: true }, error: { enumerable: true } }), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(WritableStreamDefaultController.prototype, Symbol.toStringTag, { value: "WritableStreamDefaultController", configurable: true });
var dr = "undefined" != typeof globalThis ? globalThis : "undefined" != typeof self ? self : "undefined" != typeof global ? global : void 0;
var fr = (function() {
  const e2 = null == dr ? void 0 : dr.DOMException;
  return (function(e3) {
    if ("function" != typeof e3 && "object" != typeof e3) return false;
    if ("DOMException" !== e3.name) return false;
    try {
      return new e3(), true;
    } catch (e4) {
      return false;
    }
  })(e2) ? e2 : void 0;
})() || (function() {
  const e2 = function(e3, t2) {
    this.message = e3 || "", this.name = t2 || "Error", Error.captureStackTrace && Error.captureStackTrace(this, this.constructor);
  };
  return o(e2, "DOMException"), e2.prototype = Object.create(Error.prototype), Object.defineProperty(e2.prototype, "constructor", { value: e2, writable: true, configurable: true }), e2;
})();
function hr(e2, t2, r2, o2, n2, i2) {
  const a2 = V(e2), s2 = Pt(t2);
  e2._disturbed = true;
  const l2 = new br(s2), _2 = new mr(l2);
  return u((m2, y2) => {
    let S2;
    if (void 0 !== i2) {
      if (S2 = () => {
        const r3 = void 0 !== i2.reason ? i2.reason : new fr("Aborted", "AbortError"), a3 = [];
        o2 || a3.push(() => "writable" === t2._state ? Wt(t2, r3) : c(void 0)), n2 || a3.push(() => "readable" === e2._state ? Mr(e2, r3) : c(void 0)), T2(() => Promise.all(a3.map((e3) => e3())), true, r3);
      }, i2.aborted) return void S2();
      i2.addEventListener("abort", S2);
    }
    function g2() {
      for (; !l2._shuttingDown && !t2._backpressure && "writable" === t2._state && !At(t2) && "readable" === e2._state && re(a2); ) te(a2, _2);
      if (l2._shuttingDown) return c(true);
      if (t2._backpressure) return f(s2._readyPromise, g2);
      const r3 = new _r(l2);
      return te(a2, r3), r3._promise;
    }
    var v2, w2, R2;
    if (pr(e2, a2._closedPromise, (e3) => (o2 ? P2(true, e3) : T2(() => Wt(t2, e3), true, e3), null)), pr(t2, s2._closedPromise, (t3) => (n2 ? P2(true, t3) : T2(() => Mr(e2, t3), true, t3), null)), v2 = e2, w2 = a2._closedPromise, R2 = () => (r2 ? P2() : T2(() => (function(e3) {
      const t3 = e3._ownerWritableStream, r3 = t3._state;
      return At(t3) || "closed" === r3 ? c(void 0) : "errored" === r3 ? d(t3._storedError) : Lt(e3);
    })(s2)), null), "closed" === v2._state ? R2() : b(w2, R2), At(t2) || "closed" === t2._state) {
      const t3 = new TypeError("the destination writable stream closed before all data could be piped to it");
      n2 ? P2(true, t3) : T2(() => Mr(e2, t3), true, t3);
    }
    function T2(e3, r3, o3) {
      function n3() {
        return h(e3(), () => C2(r3, o3), (e4) => C2(true, e4)), null;
      }
      l2._shuttingDown || (l2._shuttingDown = true, "writable" !== t2._state || At(t2) ? n3() : b(l2._waitForWritesToFinish(), n3));
    }
    function P2(e3, r3) {
      l2._shuttingDown || (l2._shuttingDown = true, "writable" !== t2._state || At(t2) ? C2(e3, r3) : b(l2._waitForWritesToFinish(), () => C2(e3, r3)));
    }
    function C2(e3, t3) {
      return Mt(s2), O(a2), void 0 !== i2 && i2.removeEventListener("abort", S2), e3 ? y2(t3) : m2(void 0), null;
    }
    p(u((e3, t3) => {
      !(function r3(o3) {
        o3 ? e3() : f(g2(), r3, t3);
      })(false);
    }));
  });
}
var br = class {
  constructor(e2) {
    this._writer = e2, this._shuttingDown = false, this._currentWrite = c(void 0);
  }
  _waitForWritesToFinish() {
    const e2 = this._currentWrite;
    return f(this._currentWrite, () => e2 !== this._currentWrite ? this._waitForWritesToFinish() : void 0);
  }
};
var _r = class {
  constructor(e2) {
    this._state = e2, this._promise = u((e3, t2) => {
      this._resolvePromise = e3, this._rejectPromise = t2;
    });
  }
  _chunkSteps(t2) {
    this._state._currentWrite = f(Yt(this._state._writer, t2), void 0, e), this._resolvePromise(false);
  }
  _closeSteps() {
    this._resolvePromise(true);
  }
  _errorSteps(e2) {
    this._rejectPromise(e2);
  }
};
var mr = class {
  constructor(e2) {
    this._state = e2;
  }
  _chunkSteps(t2) {
    this._state._currentWrite = f(Yt(this._state._writer, t2), void 0, e);
  }
  _closeSteps() {
  }
  _errorSteps(e2) {
  }
};
function pr(e2, t2, r2) {
  "errored" === e2._state ? r2(e2._storedError) : _(t2, r2);
}
var ReadableStreamDefaultController = class {
  constructor() {
    throw new TypeError("Illegal constructor");
  }
  get desiredSize() {
    if (!yr(this)) throw Er("desiredSize");
    return Pr(this);
  }
  close() {
    if (!yr(this)) throw Er("close");
    if (!Cr(this)) throw new TypeError("The stream is not in a state that permits close");
    wr(this);
  }
  enqueue(e2 = void 0) {
    if (!yr(this)) throw Er("enqueue");
    if (!Cr(this)) throw new TypeError("The stream is not in a state that permits enqueue");
    return Rr(this, e2);
  }
  error(e2 = void 0) {
    if (!yr(this)) throw Er("error");
    Tr(this, e2);
  }
  [T](e2) {
    qe(this);
    const t2 = this._cancelAlgorithm(e2);
    return vr(this), t2;
  }
  [P](e2) {
    const t2 = this._controlledReadableStream;
    if (this._queue.length > 0) {
      const r2 = Pe(this);
      this._closeRequested && 0 === this._queue.length ? (vr(this), Yr(t2)) : Sr(this), e2._chunkSteps(r2);
    } else U(t2, e2), Sr(this);
  }
  [C]() {
    return this._queue.length > 0;
  }
  [q]() {
  }
};
function yr(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_controlledReadableStream") && e2 instanceof ReadableStreamDefaultController);
}
function Sr(e2) {
  if (!gr(e2)) return;
  if (e2._pulling) return void (e2._pullAgain = true);
  e2._pulling = true;
  h(e2._pullAlgorithm(), () => (e2._pulling = false, e2._pullAgain && (e2._pullAgain = false, Sr(e2)), null), (t2) => (Tr(e2, t2), null));
}
function gr(e2) {
  const t2 = e2._controlledReadableStream;
  if (!Cr(e2)) return false;
  if (!e2._started) return false;
  if ($r(t2) && X(t2) > 0) return true;
  return Pr(e2) > 0;
}
function vr(e2) {
  e2._pullAlgorithm = void 0, e2._cancelAlgorithm = void 0, e2._strategySizeAlgorithm = void 0;
}
function wr(e2) {
  if (!Cr(e2)) return;
  const t2 = e2._controlledReadableStream;
  e2._closeRequested = true, 0 === e2._queue.length && (vr(e2), Yr(t2));
}
function Rr(e2, t2) {
  if (!Cr(e2)) return;
  const r2 = e2._controlledReadableStream;
  if ($r(r2) && X(r2) > 0) G(r2, t2, false);
  else {
    let r3;
    try {
      r3 = e2._strategySizeAlgorithm(t2);
    } catch (t3) {
      throw Tr(e2, t3), t3;
    }
    try {
      Ce(e2, t2, r3);
    } catch (t3) {
      throw Tr(e2, t3), t3;
    }
  }
  Sr(e2);
}
function Tr(e2, t2) {
  const r2 = e2._controlledReadableStream;
  "readable" === r2._state && (qe(e2), vr(e2), xr(r2, t2));
}
function Pr(e2) {
  const t2 = e2._controlledReadableStream._state;
  return "errored" === t2 ? null : "closed" === t2 ? 0 : e2._strategyHWM - e2._queueTotalSize;
}
function Cr(e2) {
  const t2 = e2._controlledReadableStream._state;
  return !e2._closeRequested && "readable" === t2;
}
function qr(e2, t2, r2, o2, n2, i2, a2) {
  t2._controlledReadableStream = e2, t2._queue = void 0, t2._queueTotalSize = void 0, qe(t2), t2._started = false, t2._closeRequested = false, t2._pullAgain = false, t2._pulling = false, t2._strategySizeAlgorithm = a2, t2._strategyHWM = i2, t2._pullAlgorithm = o2, t2._cancelAlgorithm = n2, e2._readableStreamController = t2;
  h(c(r2()), () => (t2._started = true, Sr(t2), null), (e3) => (Tr(t2, e3), null));
}
function Er(e2) {
  return new TypeError(`ReadableStreamDefaultController.prototype.${e2} can only be used on a ReadableStreamDefaultController`);
}
function Wr(e2, t2) {
  return Oe(e2._readableStreamController) ? (function(e3) {
    let t3, r2, o2, n2, i2, a2 = V(e3), s2 = false, l2 = false, d2 = false, f2 = false, h2 = false;
    const b2 = u((e4) => {
      i2 = e4;
    });
    function m2(e4) {
      _(e4._closedPromise, (t4) => (e4 !== a2 || (Xe(o2._readableStreamController, t4), Xe(n2._readableStreamController, t4), f2 && h2 || i2(void 0)), null));
    }
    function p2() {
      ft(a2) && (O(a2), a2 = V(e3), m2(a2));
      te(a2, { _chunkSteps: (t4) => {
        y(() => {
          l2 = false, d2 = false;
          const r3 = t4;
          let a3 = t4;
          if (!f2 && !h2) try {
            a3 = Te(t4);
          } catch (t5) {
            return Xe(o2._readableStreamController, t5), Xe(n2._readableStreamController, t5), void i2(Mr(e3, t5));
          }
          f2 || Ge(o2._readableStreamController, r3), h2 || Ge(n2._readableStreamController, a3), s2 = false, l2 ? g2() : d2 && v2();
        });
      }, _closeSteps: () => {
        s2 = false, f2 || Ue(o2._readableStreamController), h2 || Ue(n2._readableStreamController), o2._readableStreamController._pendingPullIntos.length > 0 && et(o2._readableStreamController, 0), n2._readableStreamController._pendingPullIntos.length > 0 && et(n2._readableStreamController, 0), f2 && h2 || i2(void 0);
      }, _errorSteps: () => {
        s2 = false;
      } });
    }
    function S2(t4, r3) {
      ee(a2) && (O(a2), a2 = at(e3), m2(a2));
      const u2 = r3 ? n2 : o2, c2 = r3 ? o2 : n2;
      ht(a2, t4, 1, { _chunkSteps: (t5) => {
        y(() => {
          l2 = false, d2 = false;
          const o3 = r3 ? h2 : f2;
          if (r3 ? f2 : h2) o3 || tt(u2._readableStreamController, t5);
          else {
            let r4;
            try {
              r4 = Te(t5);
            } catch (t6) {
              return Xe(u2._readableStreamController, t6), Xe(c2._readableStreamController, t6), void i2(Mr(e3, t6));
            }
            o3 || tt(u2._readableStreamController, t5), Ge(c2._readableStreamController, r4);
          }
          s2 = false, l2 ? g2() : d2 && v2();
        });
      }, _closeSteps: (e4) => {
        s2 = false;
        const t5 = r3 ? h2 : f2, o3 = r3 ? f2 : h2;
        t5 || Ue(u2._readableStreamController), o3 || Ue(c2._readableStreamController), void 0 !== e4 && (t5 || tt(u2._readableStreamController, e4), !o3 && c2._readableStreamController._pendingPullIntos.length > 0 && et(c2._readableStreamController, 0)), t5 && o3 || i2(void 0);
      }, _errorSteps: () => {
        s2 = false;
      } });
    }
    function g2() {
      if (s2) return l2 = true, c(void 0);
      s2 = true;
      const e4 = Ke(o2._readableStreamController);
      return null === e4 ? p2() : S2(e4._view, false), c(void 0);
    }
    function v2() {
      if (s2) return d2 = true, c(void 0);
      s2 = true;
      const e4 = Ke(n2._readableStreamController);
      return null === e4 ? p2() : S2(e4._view, true), c(void 0);
    }
    function w2(o3) {
      if (f2 = true, t3 = o3, h2) {
        const o4 = le([t3, r2]), n3 = Mr(e3, o4);
        i2(n3);
      }
      return b2;
    }
    function R2(o3) {
      if (h2 = true, r2 = o3, f2) {
        const o4 = le([t3, r2]), n3 = Mr(e3, o4);
        i2(n3);
      }
      return b2;
    }
    function T2() {
    }
    return o2 = Fr(T2, g2, w2), n2 = Fr(T2, v2, R2), m2(a2), [o2, n2];
  })(e2) : (function(e3) {
    const t3 = V(e3);
    let r2, o2, n2, i2, a2, s2 = false, l2 = false, d2 = false, f2 = false;
    const h2 = u((e4) => {
      a2 = e4;
    });
    function b2() {
      if (s2) return l2 = true, c(void 0);
      s2 = true;
      return te(t3, { _chunkSteps: (e4) => {
        y(() => {
          l2 = false;
          const t4 = e4, r3 = e4;
          d2 || Rr(n2._readableStreamController, t4), f2 || Rr(i2._readableStreamController, r3), s2 = false, l2 && b2();
        });
      }, _closeSteps: () => {
        s2 = false, d2 || wr(n2._readableStreamController), f2 || wr(i2._readableStreamController), d2 && f2 || a2(void 0);
      }, _errorSteps: () => {
        s2 = false;
      } }), c(void 0);
    }
    function m2(t4) {
      if (d2 = true, r2 = t4, f2) {
        const t5 = le([r2, o2]), n3 = Mr(e3, t5);
        a2(n3);
      }
      return h2;
    }
    function p2(t4) {
      if (f2 = true, o2 = t4, d2) {
        const t5 = le([r2, o2]), n3 = Mr(e3, t5);
        a2(n3);
      }
      return h2;
    }
    function S2() {
    }
    return n2 = Dr(S2, b2, m2), i2 = Dr(S2, b2, p2), _(t3._closedPromise, (e4) => (Tr(n2._readableStreamController, e4), Tr(i2._readableStreamController, e4), d2 && f2 || a2(void 0), null)), [n2, i2];
  })(e2);
}
function Or(r2) {
  return t(o2 = r2) && void 0 !== o2.getReader ? (function(r3) {
    let o3;
    function n2() {
      let e2;
      try {
        e2 = r3.read();
      } catch (e3) {
        return d(e3);
      }
      return m(e2, (e3) => {
        if (!t(e3)) throw new TypeError("The promise returned by the reader.read() method must fulfill with an object");
        if (e3.done) wr(o3._readableStreamController);
        else {
          const t2 = e3.value;
          Rr(o3._readableStreamController, t2);
        }
      });
    }
    function i2(e2) {
      try {
        return c(r3.cancel(e2));
      } catch (e3) {
        return d(e3);
      }
    }
    return o3 = Dr(e, n2, i2, 0), o3;
  })(r2.getReader()) : (function(r3) {
    let o3;
    const n2 = me(r3, "async");
    function i2() {
      let e2;
      try {
        e2 = pe(n2);
      } catch (e3) {
        return d(e3);
      }
      return m(c(e2), (e3) => {
        if (!t(e3)) throw new TypeError("The promise returned by the iterator.next() method must fulfill with an object");
        if (e3.done) wr(o3._readableStreamController);
        else {
          const t2 = e3.value;
          Rr(o3._readableStreamController, t2);
        }
      });
    }
    function a2(e2) {
      const r4 = n2.iterator;
      let o4;
      try {
        o4 = he(r4, "return");
      } catch (e3) {
        return d(e3);
      }
      if (void 0 === o4) return c(void 0);
      return m(g(o4, r4, [e2]), (e3) => {
        if (!t(e3)) throw new TypeError("The promise returned by the iterator.return() method must fulfill with an object");
      });
    }
    return o3 = Dr(e, i2, a2, 0), o3;
  })(r2);
  var o2;
}
function Br(e2, t2, r2) {
  return I(e2, r2), (r3) => g(e2, t2, [r3]);
}
function jr(e2, t2, r2) {
  return I(e2, r2), (r3) => g(e2, t2, [r3]);
}
function kr(e2, t2, r2) {
  return I(e2, r2), (r3) => S(e2, t2, [r3]);
}
function Ar(e2, t2) {
  if ("bytes" !== (e2 = `${e2}`)) throw new TypeError(`${t2} '${e2}' is not a valid enumeration value for ReadableStreamType`);
  return e2;
}
function zr(e2, t2) {
  L(e2, t2);
  const r2 = null == e2 ? void 0 : e2.preventAbort, o2 = null == e2 ? void 0 : e2.preventCancel, n2 = null == e2 ? void 0 : e2.preventClose, i2 = null == e2 ? void 0 : e2.signal;
  return void 0 !== i2 && (function(e3, t3) {
    if (!(function(e4) {
      if ("object" != typeof e4 || null === e4) return false;
      try {
        return "boolean" == typeof e4.aborted;
      } catch (e5) {
        return false;
      }
    })(e3)) throw new TypeError(`${t3} is not an AbortSignal.`);
  })(i2, `${t2} has member 'signal' that`), { preventAbort: Boolean(r2), preventCancel: Boolean(o2), preventClose: Boolean(n2), signal: i2 };
}
Object.defineProperties(ReadableStreamDefaultController.prototype, { close: { enumerable: true }, enqueue: { enumerable: true }, error: { enumerable: true }, desiredSize: { enumerable: true } }), o(ReadableStreamDefaultController.prototype.close, "close"), o(ReadableStreamDefaultController.prototype.enqueue, "enqueue"), o(ReadableStreamDefaultController.prototype.error, "error"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableStreamDefaultController.prototype, Symbol.toStringTag, { value: "ReadableStreamDefaultController", configurable: true });
var ReadableStream2 = class {
  constructor(e2 = {}, t2 = {}) {
    void 0 === e2 ? e2 = null : $(e2, "First parameter");
    const r2 = yt(t2, "Second parameter"), o2 = (function(e3, t3) {
      L(e3, t3);
      const r3 = e3, o3 = null == r3 ? void 0 : r3.autoAllocateChunkSize, n2 = null == r3 ? void 0 : r3.cancel, i2 = null == r3 ? void 0 : r3.pull, a2 = null == r3 ? void 0 : r3.start, s2 = null == r3 ? void 0 : r3.type;
      return { autoAllocateChunkSize: void 0 === o3 ? void 0 : N(o3, `${t3} has member 'autoAllocateChunkSize' that`), cancel: void 0 === n2 ? void 0 : Br(n2, r3, `${t3} has member 'cancel' that`), pull: void 0 === i2 ? void 0 : jr(i2, r3, `${t3} has member 'pull' that`), start: void 0 === a2 ? void 0 : kr(a2, r3, `${t3} has member 'start' that`), type: void 0 === s2 ? void 0 : Ar(s2, `${t3} has member 'type' that`) };
    })(e2, "First parameter");
    if (Lr(this), "bytes" === o2.type) {
      if (void 0 !== r2.size) throw new RangeError("The strategy for a byte stream cannot have a size function");
      !(function(e3, t3, r3) {
        const o3 = Object.create(ReadableByteStreamController.prototype);
        let n2, i2, a2;
        n2 = void 0 !== t3.start ? () => t3.start(o3) : () => {
        }, i2 = void 0 !== t3.pull ? () => t3.pull(o3) : () => c(void 0), a2 = void 0 !== t3.cancel ? (e4) => t3.cancel(e4) : () => c(void 0);
        const s2 = t3.autoAllocateChunkSize;
        if (0 === s2) throw new TypeError("autoAllocateChunkSize must be greater than 0");
        rt(e3, o3, n2, i2, a2, r3, s2);
      })(this, o2, mt(r2, 0));
    } else {
      const e3 = pt(r2);
      !(function(e4, t3, r3, o3) {
        const n2 = Object.create(ReadableStreamDefaultController.prototype);
        let i2, a2, s2;
        i2 = void 0 !== t3.start ? () => t3.start(n2) : () => {
        }, a2 = void 0 !== t3.pull ? () => t3.pull(n2) : () => c(void 0), s2 = void 0 !== t3.cancel ? (e5) => t3.cancel(e5) : () => c(void 0), qr(e4, n2, i2, a2, s2, r3, o3);
      })(this, o2, mt(r2, 1), e3);
    }
  }
  get locked() {
    if (!Ir(this)) throw Qr("locked");
    return $r(this);
  }
  cancel(e2 = void 0) {
    return Ir(this) ? $r(this) ? d(new TypeError("Cannot cancel a stream that already has a reader")) : Mr(this, e2) : d(Qr("cancel"));
  }
  getReader(e2 = void 0) {
    if (!Ir(this)) throw Qr("getReader");
    return void 0 === (function(e3, t2) {
      L(e3, t2);
      const r2 = null == e3 ? void 0 : e3.mode;
      return { mode: void 0 === r2 ? void 0 : it(r2, `${t2} has member 'mode' that`) };
    })(e2, "First parameter").mode ? V(this) : at(this);
  }
  pipeThrough(e2, t2 = {}) {
    if (!Ir(this)) throw Qr("pipeThrough");
    M(e2, 1, "pipeThrough");
    const r2 = (function(e3, t3) {
      L(e3, t3);
      const r3 = null == e3 ? void 0 : e3.readable;
      Y(r3, "readable", "ReadableWritablePair"), H(r3, `${t3} has member 'readable' that`);
      const o3 = null == e3 ? void 0 : e3.writable;
      return Y(o3, "writable", "ReadableWritablePair"), Tt(o3, `${t3} has member 'writable' that`), { readable: r3, writable: o3 };
    })(e2, "First parameter"), o2 = zr(t2, "Second parameter");
    if ($r(this)) throw new TypeError("ReadableStream.prototype.pipeThrough cannot be used on a locked ReadableStream");
    if (Et(r2.writable)) throw new TypeError("ReadableStream.prototype.pipeThrough cannot be used on a locked WritableStream");
    return p(hr(this, r2.writable, o2.preventClose, o2.preventAbort, o2.preventCancel, o2.signal)), r2.readable;
  }
  pipeTo(e2, t2 = {}) {
    if (!Ir(this)) return d(Qr("pipeTo"));
    if (void 0 === e2) return d("Parameter 1 is required in 'pipeTo'.");
    if (!qt(e2)) return d(new TypeError("ReadableStream.prototype.pipeTo's first argument must be a WritableStream"));
    let r2;
    try {
      r2 = zr(t2, "Second parameter");
    } catch (e3) {
      return d(e3);
    }
    return $r(this) ? d(new TypeError("ReadableStream.prototype.pipeTo cannot be used on a locked ReadableStream")) : Et(e2) ? d(new TypeError("ReadableStream.prototype.pipeTo cannot be used on a locked WritableStream")) : hr(this, e2, r2.preventClose, r2.preventAbort, r2.preventCancel, r2.signal);
  }
  tee() {
    if (!Ir(this)) throw Qr("tee");
    return le(Wr(this));
  }
  values(e2 = void 0) {
    if (!Ir(this)) throw Qr("values");
    return (function(e3, t2) {
      const r2 = V(e3), o2 = new ye(r2, t2), n2 = Object.create(ge);
      return n2._asyncIteratorImpl = o2, n2;
    })(this, (function(e3, t2) {
      L(e3, t2);
      const r2 = null == e3 ? void 0 : e3.preventCancel;
      return { preventCancel: Boolean(r2) };
    })(e2, "First parameter").preventCancel);
  }
  [_e](e2) {
    return this.values(e2);
  }
  static from(e2) {
    return Or(e2);
  }
};
function Dr(e2, t2, r2, o2 = 1, n2 = () => 1) {
  const i2 = Object.create(ReadableStream2.prototype);
  Lr(i2);
  return qr(i2, Object.create(ReadableStreamDefaultController.prototype), e2, t2, r2, o2, n2), i2;
}
function Fr(e2, t2, r2) {
  const o2 = Object.create(ReadableStream2.prototype);
  Lr(o2);
  return rt(o2, Object.create(ReadableByteStreamController.prototype), e2, t2, r2, 0, void 0), o2;
}
function Lr(e2) {
  e2._state = "readable", e2._reader = void 0, e2._storedError = void 0, e2._disturbed = false;
}
function Ir(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_readableStreamController") && e2 instanceof ReadableStream2);
}
function $r(e2) {
  return void 0 !== e2._reader;
}
function Mr(t2, r2) {
  if (t2._disturbed = true, "closed" === t2._state) return c(void 0);
  if ("errored" === t2._state) return d(t2._storedError);
  Yr(t2);
  const o2 = t2._reader;
  if (void 0 !== o2 && ft(o2)) {
    const e2 = o2._readIntoRequests;
    o2._readIntoRequests = new v(), e2.forEach((e3) => {
      e3._closeSteps(void 0);
    });
  }
  return m(t2._readableStreamController[T](r2), e);
}
function Yr(e2) {
  e2._state = "closed";
  const t2 = e2._reader;
  if (void 0 !== t2 && (z(t2), ee(t2))) {
    const e3 = t2._readRequests;
    t2._readRequests = new v(), e3.forEach((e4) => {
      e4._closeSteps();
    });
  }
}
function xr(e2, t2) {
  e2._state = "errored", e2._storedError = t2;
  const r2 = e2._reader;
  void 0 !== r2 && (A(r2, t2), ee(r2) ? oe(r2, t2) : bt(r2, t2));
}
function Qr(e2) {
  return new TypeError(`ReadableStream.prototype.${e2} can only be used on a ReadableStream`);
}
function Nr(e2, t2) {
  L(e2, t2);
  const r2 = null == e2 ? void 0 : e2.highWaterMark;
  return Y(r2, "highWaterMark", "QueuingStrategyInit"), { highWaterMark: x(r2) };
}
Object.defineProperties(ReadableStream2, { from: { enumerable: true } }), Object.defineProperties(ReadableStream2.prototype, { cancel: { enumerable: true }, getReader: { enumerable: true }, pipeThrough: { enumerable: true }, pipeTo: { enumerable: true }, tee: { enumerable: true }, values: { enumerable: true }, locked: { enumerable: true } }), o(ReadableStream2.from, "from"), o(ReadableStream2.prototype.cancel, "cancel"), o(ReadableStream2.prototype.getReader, "getReader"), o(ReadableStream2.prototype.pipeThrough, "pipeThrough"), o(ReadableStream2.prototype.pipeTo, "pipeTo"), o(ReadableStream2.prototype.tee, "tee"), o(ReadableStream2.prototype.values, "values"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ReadableStream2.prototype, Symbol.toStringTag, { value: "ReadableStream", configurable: true }), Object.defineProperty(ReadableStream2.prototype, _e, { value: ReadableStream2.prototype.values, writable: true, configurable: true });
var Hr = (e2) => e2.byteLength;
o(Hr, "size");
var ByteLengthQueuingStrategy = class {
  constructor(e2) {
    M(e2, 1, "ByteLengthQueuingStrategy"), e2 = Nr(e2, "First parameter"), this._byteLengthQueuingStrategyHighWaterMark = e2.highWaterMark;
  }
  get highWaterMark() {
    if (!Ur(this)) throw Vr("highWaterMark");
    return this._byteLengthQueuingStrategyHighWaterMark;
  }
  get size() {
    if (!Ur(this)) throw Vr("size");
    return Hr;
  }
};
function Vr(e2) {
  return new TypeError(`ByteLengthQueuingStrategy.prototype.${e2} can only be used on a ByteLengthQueuingStrategy`);
}
function Ur(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_byteLengthQueuingStrategyHighWaterMark") && e2 instanceof ByteLengthQueuingStrategy);
}
Object.defineProperties(ByteLengthQueuingStrategy.prototype, { highWaterMark: { enumerable: true }, size: { enumerable: true } }), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(ByteLengthQueuingStrategy.prototype, Symbol.toStringTag, { value: "ByteLengthQueuingStrategy", configurable: true });
var Gr = () => 1;
o(Gr, "size");
var CountQueuingStrategy = class {
  constructor(e2) {
    M(e2, 1, "CountQueuingStrategy"), e2 = Nr(e2, "First parameter"), this._countQueuingStrategyHighWaterMark = e2.highWaterMark;
  }
  get highWaterMark() {
    if (!Jr(this)) throw Xr("highWaterMark");
    return this._countQueuingStrategyHighWaterMark;
  }
  get size() {
    if (!Jr(this)) throw Xr("size");
    return Gr;
  }
};
function Xr(e2) {
  return new TypeError(`CountQueuingStrategy.prototype.${e2} can only be used on a CountQueuingStrategy`);
}
function Jr(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_countQueuingStrategyHighWaterMark") && e2 instanceof CountQueuingStrategy);
}
function Kr(e2, t2, r2) {
  return I(e2, r2), (r3) => g(e2, t2, [r3]);
}
function Zr(e2, t2, r2) {
  return I(e2, r2), (r3) => S(e2, t2, [r3]);
}
function eo(e2, t2, r2) {
  return I(e2, r2), (r3, o2) => g(e2, t2, [r3, o2]);
}
function to(e2, t2, r2) {
  return I(e2, r2), (r3) => g(e2, t2, [r3]);
}
Object.defineProperties(CountQueuingStrategy.prototype, { highWaterMark: { enumerable: true }, size: { enumerable: true } }), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(CountQueuingStrategy.prototype, Symbol.toStringTag, { value: "CountQueuingStrategy", configurable: true });
var TransformStream2 = class {
  constructor(e2 = {}, t2 = {}, r2 = {}) {
    void 0 === e2 && (e2 = null);
    const o2 = yt(t2, "Second parameter"), n2 = yt(r2, "Third parameter"), i2 = (function(e3, t3) {
      L(e3, t3);
      const r3 = null == e3 ? void 0 : e3.cancel, o3 = null == e3 ? void 0 : e3.flush, n3 = null == e3 ? void 0 : e3.readableType, i3 = null == e3 ? void 0 : e3.start, a3 = null == e3 ? void 0 : e3.transform, s3 = null == e3 ? void 0 : e3.writableType;
      return { cancel: void 0 === r3 ? void 0 : to(r3, e3, `${t3} has member 'cancel' that`), flush: void 0 === o3 ? void 0 : Kr(o3, e3, `${t3} has member 'flush' that`), readableType: n3, start: void 0 === i3 ? void 0 : Zr(i3, e3, `${t3} has member 'start' that`), transform: void 0 === a3 ? void 0 : eo(a3, e3, `${t3} has member 'transform' that`), writableType: s3 };
    })(e2, "First parameter");
    if (void 0 !== i2.readableType) throw new RangeError("Invalid readableType specified");
    if (void 0 !== i2.writableType) throw new RangeError("Invalid writableType specified");
    const a2 = mt(n2, 0), s2 = pt(n2), l2 = mt(o2, 1), f2 = pt(o2);
    let b2;
    !(function(e3, t3, r3, o3, n3, i3) {
      function a3() {
        return t3;
      }
      function s3(t4) {
        return (function(e4, t5) {
          const r4 = e4._transformStreamController;
          if (e4._backpressure) {
            return m(e4._backpressureChangePromise, () => {
              const o4 = e4._writable;
              if ("erroring" === o4._state) throw o4._storedError;
              return co(r4, t5);
            });
          }
          return co(r4, t5);
        })(e3, t4);
      }
      function l3(t4) {
        return (function(e4, t5) {
          const r4 = e4._transformStreamController;
          if (void 0 !== r4._finishPromise) return r4._finishPromise;
          const o4 = e4._readable;
          r4._finishPromise = u((e5, t6) => {
            r4._finishPromise_resolve = e5, r4._finishPromise_reject = t6;
          });
          const n4 = r4._cancelAlgorithm(t5);
          return lo(r4), h(n4, () => ("errored" === o4._state ? bo(r4, o4._storedError) : (Tr(o4._readableStreamController, t5), ho(r4)), null), (e5) => (Tr(o4._readableStreamController, e5), bo(r4, e5), null)), r4._finishPromise;
        })(e3, t4);
      }
      function c2() {
        return (function(e4) {
          const t4 = e4._transformStreamController;
          if (void 0 !== t4._finishPromise) return t4._finishPromise;
          const r4 = e4._readable;
          t4._finishPromise = u((e5, r5) => {
            t4._finishPromise_resolve = e5, t4._finishPromise_reject = r5;
          });
          const o4 = t4._flushAlgorithm();
          return lo(t4), h(o4, () => ("errored" === r4._state ? bo(t4, r4._storedError) : (wr(r4._readableStreamController), ho(t4)), null), (e5) => (Tr(r4._readableStreamController, e5), bo(t4, e5), null)), t4._finishPromise;
        })(e3);
      }
      function d2() {
        return (function(e4) {
          return ao(e4, false), e4._backpressureChangePromise;
        })(e3);
      }
      function f3(t4) {
        return (function(e4, t5) {
          const r4 = e4._transformStreamController;
          if (void 0 !== r4._finishPromise) return r4._finishPromise;
          const o4 = e4._writable;
          r4._finishPromise = u((e5, t6) => {
            r4._finishPromise_resolve = e5, r4._finishPromise_reject = t6;
          });
          const n4 = r4._cancelAlgorithm(t5);
          return lo(r4), h(n4, () => ("errored" === o4._state ? bo(r4, o4._storedError) : (Gt(o4._writableStreamController, t5), io(e4), ho(r4)), null), (t6) => (Gt(o4._writableStreamController, t6), io(e4), bo(r4, t6), null)), r4._finishPromise;
        })(e3, t4);
      }
      e3._writable = (function(e4, t4, r4, o4, n4 = 1, i4 = () => 1) {
        const a4 = Object.create(WritableStream2.prototype);
        return Ct(a4), Nt(a4, Object.create(WritableStreamDefaultController.prototype), e4, t4, r4, o4, n4, i4), a4;
      })(a3, s3, c2, l3, r3, o3), e3._readable = Dr(a3, d2, f3, n3, i3), e3._backpressure = void 0, e3._backpressureChangePromise = void 0, e3._backpressureChangePromise_resolve = void 0, ao(e3, true), e3._transformStreamController = void 0;
    })(this, u((e3) => {
      b2 = e3;
    }), l2, f2, a2, s2), (function(e3, t3) {
      const r3 = Object.create(TransformStreamDefaultController.prototype);
      let o3, n3, i3;
      o3 = void 0 !== t3.transform ? (e4) => t3.transform(e4, r3) : (e4) => {
        try {
          return uo(r3, e4), c(void 0);
        } catch (e5) {
          return d(e5);
        }
      };
      n3 = void 0 !== t3.flush ? () => t3.flush(r3) : () => c(void 0);
      i3 = void 0 !== t3.cancel ? (e4) => t3.cancel(e4) : () => c(void 0);
      !(function(e4, t4, r4, o4, n4) {
        t4._controlledTransformStream = e4, e4._transformStreamController = t4, t4._transformAlgorithm = r4, t4._flushAlgorithm = o4, t4._cancelAlgorithm = n4, t4._finishPromise = void 0, t4._finishPromise_resolve = void 0, t4._finishPromise_reject = void 0;
      })(e3, r3, o3, n3, i3);
    })(this, i2), void 0 !== i2.start ? b2(i2.start(this._transformStreamController)) : b2(void 0);
  }
  get readable() {
    if (!ro(this)) throw _o("readable");
    return this._readable;
  }
  get writable() {
    if (!ro(this)) throw _o("writable");
    return this._writable;
  }
};
function ro(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_transformStreamController") && e2 instanceof TransformStream2);
}
function oo(e2, t2) {
  Tr(e2._readable._readableStreamController, t2), no(e2, t2);
}
function no(e2, t2) {
  lo(e2._transformStreamController), Gt(e2._writable._writableStreamController, t2), io(e2);
}
function io(e2) {
  e2._backpressure && ao(e2, false);
}
function ao(e2, t2) {
  void 0 !== e2._backpressureChangePromise && e2._backpressureChangePromise_resolve(), e2._backpressureChangePromise = u((t3) => {
    e2._backpressureChangePromise_resolve = t3;
  }), e2._backpressure = t2;
}
Object.defineProperties(TransformStream2.prototype, { readable: { enumerable: true }, writable: { enumerable: true } }), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(TransformStream2.prototype, Symbol.toStringTag, { value: "TransformStream", configurable: true });
var TransformStreamDefaultController = class {
  constructor() {
    throw new TypeError("Illegal constructor");
  }
  get desiredSize() {
    if (!so(this)) throw fo("desiredSize");
    return Pr(this._controlledTransformStream._readable._readableStreamController);
  }
  enqueue(e2 = void 0) {
    if (!so(this)) throw fo("enqueue");
    uo(this, e2);
  }
  error(e2 = void 0) {
    if (!so(this)) throw fo("error");
    var t2;
    t2 = e2, oo(this._controlledTransformStream, t2);
  }
  terminate() {
    if (!so(this)) throw fo("terminate");
    !(function(e2) {
      const t2 = e2._controlledTransformStream;
      wr(t2._readable._readableStreamController);
      const r2 = new TypeError("TransformStream terminated");
      no(t2, r2);
    })(this);
  }
};
function so(e2) {
  return !!t(e2) && (!!Object.prototype.hasOwnProperty.call(e2, "_controlledTransformStream") && e2 instanceof TransformStreamDefaultController);
}
function lo(e2) {
  e2._transformAlgorithm = void 0, e2._flushAlgorithm = void 0, e2._cancelAlgorithm = void 0;
}
function uo(e2, t2) {
  const r2 = e2._controlledTransformStream, o2 = r2._readable._readableStreamController;
  if (!Cr(o2)) throw new TypeError("Readable side is not in a state that permits enqueue");
  try {
    Rr(o2, t2);
  } catch (e3) {
    throw no(r2, e3), r2._readable._storedError;
  }
  const n2 = (function(e3) {
    return !gr(e3);
  })(o2);
  n2 !== r2._backpressure && ao(r2, true);
}
function co(e2, t2) {
  return m(e2._transformAlgorithm(t2), void 0, (t3) => {
    throw oo(e2._controlledTransformStream, t3), t3;
  });
}
function fo(e2) {
  return new TypeError(`TransformStreamDefaultController.prototype.${e2} can only be used on a TransformStreamDefaultController`);
}
function ho(e2) {
  void 0 !== e2._finishPromise_resolve && (e2._finishPromise_resolve(), e2._finishPromise_resolve = void 0, e2._finishPromise_reject = void 0);
}
function bo(e2, t2) {
  void 0 !== e2._finishPromise_reject && (p(e2._finishPromise), e2._finishPromise_reject(t2), e2._finishPromise_resolve = void 0, e2._finishPromise_reject = void 0);
}
function _o(e2) {
  return new TypeError(`TransformStream.prototype.${e2} can only be used on a TransformStream`);
}
Object.defineProperties(TransformStreamDefaultController.prototype, { enqueue: { enumerable: true }, error: { enumerable: true }, terminate: { enumerable: true }, desiredSize: { enumerable: true } }), o(TransformStreamDefaultController.prototype.enqueue, "enqueue"), o(TransformStreamDefaultController.prototype.error, "error"), o(TransformStreamDefaultController.prototype.terminate, "terminate"), "symbol" == typeof Symbol.toStringTag && Object.defineProperty(TransformStreamDefaultController.prototype, Symbol.toStringTag, { value: "TransformStreamDefaultController", configurable: true });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/stream-extra/esm/stream.js
var GLOBAL = globalThis;
var AbortController3 = GLOBAL.AbortController;
var ReadableStream3 = ReadableStream2;
var WritableStream3 = WritableStream2;
var TransformStream3 = TransformStream2;
if (GLOBAL.ReadableStream && GLOBAL.WritableStream && GLOBAL.TransformStream) {
  ReadableStream3 = GLOBAL.ReadableStream;
  WritableStream3 = GLOBAL.WritableStream;
  TransformStream3 = GLOBAL.TransformStream;
} else {
}

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/stream-extra/esm/consumable.js
var { console: console2 } = globalThis;
var createTask2 = console2.createTask?.bind(console2) ?? (() => ({
  run(callback) {
    return callback();
  }
}));
var Consumable2 = class {
  constructor(value) {
    __publicField(this, "task");
    __publicField(this, "resolver");
    __publicField(this, "value");
    __publicField(this, "consumed");
    this.task = createTask2("Consumable");
    this.value = value;
    this.resolver = new PromiseResolver2();
    this.consumed = this.resolver.promise;
  }
  consume() {
    this.resolver.resolve();
  }
  error(error) {
    this.resolver.reject(error);
  }
  async tryConsume(callback) {
    try {
      const result = await this.task.run(() => callback(this.value));
      this.consume();
      return result;
    } catch (e2) {
      this.resolver.reject(e2);
      throw e2;
    }
  }
};
async function enqueue(controller, chunk) {
  const output = new Consumable2(chunk);
  controller.enqueue(output);
  await output.consumed;
}
var ConsumableWritableStream2 = class extends WritableStream3 {
  static async write(writer, value) {
    const consumable = new Consumable2(value);
    await writer.write(consumable);
    await consumable.consumed;
  }
  constructor(sink, strategy) {
    let wrappedStrategy;
    if (strategy) {
      wrappedStrategy = {};
      if ("highWaterMark" in strategy) {
        wrappedStrategy.highWaterMark = strategy.highWaterMark;
      }
      if ("size" in strategy) {
        wrappedStrategy.size = (chunk) => {
          return strategy.size(chunk.value);
        };
      }
    }
    super({
      start() {
        return sink.start?.();
      },
      async write(chunk) {
        await chunk.tryConsume((value) => sink.write?.(value));
        chunk.consume();
      },
      abort(reason) {
        return sink.abort?.(reason);
      },
      close() {
        return sink.close?.();
      }
    }, wrappedStrategy);
  }
};
var ConsumableTransformStream = class extends TransformStream3 {
  constructor(transformer) {
    let wrappedController;
    super({
      async start(controller) {
        wrappedController = {
          async enqueue(chunk) {
            await enqueue(controller, chunk);
          },
          close() {
            controller.terminate();
          },
          error(reason) {
            controller.error(reason);
          }
        };
        await transformer.start?.(wrappedController);
      },
      async transform(chunk) {
        await chunk.tryConsume((value) => transformer.transform?.(value, wrappedController));
        chunk.consume();
      },
      async flush() {
        await transformer.flush?.(wrappedController);
      }
    });
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/basic/definition.js
var StructFieldDefinition = class {
  constructor(options) {
    /**
     * When `T` is a type initiated `StructFieldDefinition`,
     * use `T['TValue']` to retrieve its `TValue` type parameter.
     */
    __publicField(this, "TValue");
    /**
     * When `T` is a type initiated `StructFieldDefinition`,
     * use `T['TOmitInitKey']` to retrieve its `TOmitInitKey` type parameter.
     */
    __publicField(this, "TOmitInitKey");
    __publicField(this, "options");
    this.options = options;
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/basic/field-value.js
var StructFieldValue = class _StructFieldValue {
  constructor(definition, options, struct2, value) {
    /** Gets the definition associated with this runtime value */
    __publicField(this, "definition");
    /** Gets the options of the associated `Struct` */
    __publicField(this, "options");
    /** Gets the associated `Struct` instance */
    __publicField(this, "struct");
    __publicField(this, "value");
    this.definition = definition;
    this.options = options;
    this.struct = struct2;
    this.value = value;
  }
  get hasCustomAccessors() {
    return this.get !== _StructFieldValue.prototype.get || this.set !== _StructFieldValue.prototype.set;
  }
  /**
   * Gets size of this field. By default, it returns its `definition`'s size.
   *
   * When overridden in derived classes, can have custom logic to calculate the actual size.
   */
  getSize() {
    return this.definition.getSize();
  }
  /**
   * When implemented in derived classes, reads current field's value.
   */
  get() {
    return this.value;
  }
  /**
   * When implemented in derived classes, updates current field's value.
   */
  set(value) {
    this.value = value;
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/basic/options.js
var StructDefaultOptions = {
  littleEndian: false
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/basic/struct-value.js
var STRUCT_VALUE_SYMBOL = /* @__PURE__ */ Symbol("struct-value");
var StructValue = class {
  constructor(prototype) {
    /** @internal */
    __publicField(this, "fieldValues", {});
    /**
     * Gets the result struct value object
     */
    __publicField(this, "value");
    this.value = Object.create(prototype);
    Object.defineProperty(this.value, STRUCT_VALUE_SYMBOL, {
      enumerable: false,
      value: this
    });
  }
  /**
   * Sets a `StructFieldValue` for `key`
   *
   * @param name The field name
   * @param fieldValue The associated `StructFieldValue`
   */
  set(name, fieldValue) {
    this.fieldValues[name] = fieldValue;
    if (fieldValue.hasCustomAccessors) {
      Object.defineProperty(this.value, name, {
        configurable: true,
        enumerable: true,
        get() {
          return fieldValue.get();
        },
        set(v2) {
          fieldValue.set(v2);
        }
      });
    } else {
      this.value[name] = fieldValue.get();
    }
  }
  /**
   * Gets the `StructFieldValue` for `key`
   *
   * @param name The field name
   */
  get(name) {
    return this.fieldValues[name];
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/sync-promise.js
var SyncPromise = {
  reject(reason) {
    return new RejectedSyncPromise(reason);
  },
  resolve(value) {
    if (typeof value === "object" && value !== null && typeof value.then === "function") {
      if (value instanceof PendingSyncPromise || value instanceof ResolvedSyncPromise || value instanceof RejectedSyncPromise) {
        return value;
      }
      return new PendingSyncPromise(value);
    } else {
      return new ResolvedSyncPromise(value);
    }
  },
  try(executor) {
    try {
      return SyncPromise.resolve(executor());
    } catch (e2) {
      return SyncPromise.reject(e2);
    }
  }
};
var PendingSyncPromise = class _PendingSyncPromise {
  constructor(promise) {
    __publicField(this, "promise");
    this.promise = promise;
  }
  then(onfulfilled, onrejected) {
    return new _PendingSyncPromise(this.promise.then(onfulfilled, onrejected));
  }
  valueOrPromise() {
    return this.promise;
  }
};
var ResolvedSyncPromise = class {
  constructor(value) {
    __publicField(this, "value");
    this.value = value;
  }
  then(onfulfilled) {
    if (!onfulfilled) {
      return this;
    }
    return SyncPromise.try(() => onfulfilled(this.value));
  }
  valueOrPromise() {
    return this.value;
  }
};
var RejectedSyncPromise = class {
  constructor(reason) {
    __publicField(this, "reason");
    this.reason = reason;
  }
  then(onfulfilled, onrejected) {
    if (!onrejected) {
      return this;
    }
    return SyncPromise.try(() => onrejected(this.reason));
  }
  valueOrPromise() {
    throw this.reason;
  }
};

// node_modules/@yume-chan/dataview-bigint-polyfill/esm/pure.js
var BigInt32 = BigInt(32);
function getBigInt64(dataView, byteOffset, littleEndian) {
  const littleEndianMask = Number(!!littleEndian);
  const bigEndianMask = Number(!littleEndian);
  return BigInt(dataView.getInt32(byteOffset, littleEndian) * bigEndianMask + dataView.getInt32(byteOffset + 4, littleEndian) * littleEndianMask) << BigInt32 | BigInt(dataView.getUint32(byteOffset, littleEndian) * littleEndianMask + dataView.getUint32(byteOffset + 4, littleEndian) * bigEndianMask);
}
function getBigUint64(dataView, byteOffset, littleEndian) {
  const a2 = dataView.getUint32(byteOffset, littleEndian);
  const b2 = dataView.getUint32(byteOffset + 4, littleEndian);
  const littleEndianMask = Number(!!littleEndian);
  const bigEndianMask = Number(!littleEndian);
  return BigInt(a2 * bigEndianMask + b2 * littleEndianMask) << BigInt32 | BigInt(a2 * littleEndianMask + b2 * bigEndianMask);
}
function setBigInt64(dataView, byteOffset, value, littleEndian) {
  const hi = Number(value >> BigInt32);
  const lo2 = Number(value & BigInt(4294967295));
  if (littleEndian) {
    dataView.setInt32(byteOffset + 4, hi, littleEndian);
    dataView.setUint32(byteOffset, lo2, littleEndian);
  } else {
    dataView.setInt32(byteOffset, hi, littleEndian);
    dataView.setUint32(byteOffset + 4, lo2, littleEndian);
  }
}
function setBigUint64(dataView, byteOffset, value, littleEndian) {
  const hi = Number(value >> BigInt32);
  const lo2 = Number(value & BigInt(4294967295));
  if (littleEndian) {
    dataView.setUint32(byteOffset + 4, hi, littleEndian);
    dataView.setUint32(byteOffset, lo2, littleEndian);
  } else {
    dataView.setUint32(byteOffset, hi, littleEndian);
    dataView.setUint32(byteOffset + 4, lo2, littleEndian);
  }
}

// node_modules/@yume-chan/dataview-bigint-polyfill/esm/fallback.js
var getBigInt642 = "getBigInt64" in DataView.prototype ? (dataView, byteOffset, littleEndian) => dataView.getBigInt64(byteOffset, littleEndian) : getBigInt64;
var getBigUint642 = "getBigUint64" in DataView.prototype ? (dataView, byteOffset, littleEndian) => dataView.getBigUint64(byteOffset, littleEndian) : getBigUint64;
var setBigInt642 = "setBigInt64" in DataView.prototype ? (dataView, byteOffset, value, littleEndian) => dataView.setBigInt64(byteOffset, value, littleEndian) : setBigInt64;
var setBigUint642 = "setBigUint64" in DataView.prototype ? (dataView, byteOffset, value, littleEndian) => dataView.setBigUint64(byteOffset, value, littleEndian) : setBigUint64;

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/types/bigint.js
var _BigIntFieldType = class _BigIntFieldType {
  constructor(size, getter, setter) {
    __publicField(this, "TTypeScriptType");
    __publicField(this, "size");
    __publicField(this, "getter");
    __publicField(this, "setter");
    this.size = size;
    this.getter = getter;
    this.setter = setter;
  }
};
__publicField(_BigIntFieldType, "Int64", new _BigIntFieldType(8, getBigInt642, setBigInt642));
__publicField(_BigIntFieldType, "Uint64", new _BigIntFieldType(8, getBigUint642, setBigUint642));
var BigIntFieldType = _BigIntFieldType;
var BigIntFieldDefinition = class extends StructFieldDefinition {
  constructor(type, typescriptType) {
    void typescriptType;
    super();
    __publicField(this, "type");
    this.type = type;
  }
  getSize() {
    return this.type.size;
  }
  create(options, struct2, value) {
    return new BigIntFieldValue(this, options, struct2, value);
  }
  deserialize(options, stream, struct2) {
    return SyncPromise.try(() => {
      return stream.read(this.getSize());
    }).then((array) => {
      const view = new DataView(array.buffer, array.byteOffset, array.byteLength);
      const value = this.type.getter(view, 0, options.littleEndian);
      return this.create(options, struct2, value);
    }).valueOrPromise();
  }
};
var BigIntFieldValue = class extends StructFieldValue {
  serialize(dataView, offset) {
    this.definition.type.setter(dataView, offset, this.value, this.options.littleEndian);
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/utils.js
function placeholder() {
  return void 0;
}
var { TextEncoder: TextEncoder2, TextDecoder: TextDecoder2 } = globalThis;
var Utf8Encoder = new TextEncoder2();
var Utf8Decoder = new TextDecoder2();
function encodeUtf82(input) {
  return Utf8Encoder.encode(input);
}
function decodeUtf82(buffer2) {
  return Utf8Decoder.decode(buffer2);
}

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/types/buffer/base.js
var BufferFieldSubType = class {
  constructor() {
    __publicField(this, "TTypeScriptType");
  }
};
var _Uint8ArrayBufferFieldSubType = class _Uint8ArrayBufferFieldSubType extends BufferFieldSubType {
  constructor() {
    super();
  }
  toBuffer(value) {
    return value;
  }
  toValue(buffer2) {
    return buffer2;
  }
  getSize(value) {
    return value.byteLength;
  }
};
__publicField(_Uint8ArrayBufferFieldSubType, "Instance", new _Uint8ArrayBufferFieldSubType());
var Uint8ArrayBufferFieldSubType = _Uint8ArrayBufferFieldSubType;
var _StringBufferFieldSubType = class _StringBufferFieldSubType extends BufferFieldSubType {
  toBuffer(value) {
    return encodeUtf82(value);
  }
  toValue(array) {
    return decodeUtf82(array);
  }
  getSize() {
    return -1;
  }
};
__publicField(_StringBufferFieldSubType, "Instance", new _StringBufferFieldSubType());
var StringBufferFieldSubType = _StringBufferFieldSubType;
var EMPTY_UINT8_ARRAY = new Uint8Array(0);
var BufferLikeFieldDefinition = class extends StructFieldDefinition {
  constructor(type, options) {
    super(options);
    __publicField(this, "type");
    this.type = type;
  }
  getDeserializeSize(struct2) {
    void struct2;
    return this.getSize();
  }
  /**
   * When implemented in derived classes, creates a `StructFieldValue` for the current field definition.
   */
  create(options, struct2, value, array) {
    return new BufferLikeFieldValue(this, options, struct2, value, array);
  }
  deserialize(options, stream, struct2) {
    return SyncPromise.try(() => {
      const size = this.getDeserializeSize(struct2);
      if (size === 0) {
        return EMPTY_UINT8_ARRAY;
      } else {
        return stream.read(size);
      }
    }).then((array) => {
      const value = this.type.toValue(array);
      return this.create(options, struct2, value, array);
    }).valueOrPromise();
  }
};
var BufferLikeFieldValue = class extends StructFieldValue {
  constructor(definition, options, struct2, value, array) {
    super(definition, options, struct2, value);
    __publicField(this, "array");
    this.array = array;
  }
  set(value) {
    super.set(value);
    this.array = void 0;
  }
  serialize(dataView, offset) {
    if (!this.array) {
      this.array = this.definition.type.toBuffer(this.value);
    }
    new Uint8Array(dataView.buffer, dataView.byteOffset, dataView.byteLength).set(this.array, offset);
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/types/buffer/fixed-length.js
var FixedLengthBufferLikeFieldDefinition = class extends BufferLikeFieldDefinition {
  getSize() {
    return this.options.length;
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/types/buffer/variable-length.js
var VariableLengthBufferLikeFieldDefinition = class extends BufferLikeFieldDefinition {
  getSize() {
    return 0;
  }
  getDeserializeSize(struct2) {
    let value = struct2.value[this.options.lengthField];
    if (typeof value === "string") {
      value = Number.parseInt(value, this.options.lengthFieldRadix ?? 10);
    }
    return value;
  }
  create(options, struct2, value, array) {
    return new VariableLengthBufferLikeStructFieldValue(this, options, struct2, value, array);
  }
};
var VariableLengthBufferLikeStructFieldValue = class extends BufferLikeFieldValue {
  constructor(definition, options, struct2, value, array) {
    super(definition, options, struct2, value, array);
    __publicField(this, "length");
    __publicField(this, "lengthFieldValue");
    if (array) {
      this.length = array.byteLength;
    }
    const lengthField = this.definition.options.lengthField;
    const originalValue = struct2.get(lengthField);
    this.lengthFieldValue = new VariableLengthBufferLikeFieldLengthValue(originalValue, this);
    struct2.set(lengthField, this.lengthFieldValue);
  }
  getSize() {
    if (this.length === void 0) {
      this.length = this.definition.type.getSize(this.value);
      if (this.length === -1) {
        this.array = this.definition.type.toBuffer(this.value);
        this.length = this.array.byteLength;
      }
    }
    return this.length;
  }
  set(value) {
    super.set(value);
    this.array = void 0;
    this.length = void 0;
  }
};
var VariableLengthBufferLikeFieldLengthValue = class extends StructFieldValue {
  constructor(originalField, arrayBufferField) {
    super(originalField.definition, originalField.options, originalField.struct, 0);
    __publicField(this, "originalField");
    __publicField(this, "bufferField");
    this.originalField = originalField;
    this.bufferField = arrayBufferField;
  }
  getSize() {
    return this.originalField.getSize();
  }
  get() {
    let value = this.bufferField.getSize();
    const originalValue = this.originalField.get();
    if (typeof originalValue === "string") {
      value = value.toString(this.bufferField.definition.options.lengthFieldRadix ?? 10);
    }
    return value;
  }
  set() {
  }
  serialize(dataView, offset) {
    this.originalField.set(this.get());
    this.originalField.serialize(dataView, offset);
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/types/number.js
var NumberFieldType;
(function(NumberFieldType2) {
  NumberFieldType2.Uint8 = {
    signed: false,
    size: 1,
    deserialize(array) {
      return array[0];
    },
    serialize(dataView, offset, value) {
      dataView.setUint8(offset, value);
    }
  };
  NumberFieldType2.Int8 = {
    signed: true,
    size: 1,
    deserialize(array) {
      const value = NumberFieldType2.Uint8.deserialize(array, false);
      return value << 24 >> 24;
    },
    serialize(dataView, offset, value) {
      dataView.setInt8(offset, value);
    }
  };
  NumberFieldType2.Uint16 = {
    signed: false,
    size: 2,
    deserialize(array, littleEndian) {
      return (array[1] << 8 | array[0]) * littleEndian | (array[0] << 8 | array[1]) * !littleEndian;
    },
    serialize(dataView, offset, value, littleEndian) {
      dataView.setUint16(offset, value, littleEndian);
    }
  };
  NumberFieldType2.Int16 = {
    signed: true,
    size: 2,
    deserialize(array, littleEndian) {
      const value = NumberFieldType2.Uint16.deserialize(array, littleEndian);
      return value << 16 >> 16;
    },
    serialize(dataView, offset, value, littleEndian) {
      dataView.setInt16(offset, value, littleEndian);
    }
  };
  NumberFieldType2.Uint32 = {
    signed: false,
    size: 4,
    deserialize(array, littleEndian) {
      const value = NumberFieldType2.Int32.deserialize(array, littleEndian);
      return value >>> 0;
    },
    serialize(dataView, offset, value, littleEndian) {
      dataView.setUint32(offset, value, littleEndian);
    }
  };
  NumberFieldType2.Int32 = {
    signed: true,
    size: 4,
    deserialize(array, littleEndian) {
      return (array[3] << 24 | array[2] << 16 | array[1] << 8 | array[0]) * littleEndian | (array[0] << 24 | array[1] << 16 | array[2] << 8 | array[3]) * !littleEndian;
    },
    serialize(dataView, offset, value, littleEndian) {
      dataView.setInt32(offset, value, littleEndian);
    }
  };
})(NumberFieldType = NumberFieldType || (NumberFieldType = {}));
var NumberFieldDefinition = class extends StructFieldDefinition {
  constructor(type, typescriptType) {
    void typescriptType;
    super();
    __publicField(this, "type");
    this.type = type;
  }
  getSize() {
    return this.type.size;
  }
  create(options, struct2, value) {
    return new NumberFieldValue(this, options, struct2, value);
  }
  deserialize(options, stream, struct2) {
    return SyncPromise.try(() => {
      return stream.read(this.getSize());
    }).then((array) => {
      const value = this.type.deserialize(array, options.littleEndian);
      return this.create(options, struct2, value);
    }).valueOrPromise();
  }
};
var NumberFieldValue = class extends StructFieldValue {
  serialize(dataView, offset) {
    this.definition.type.serialize(dataView, offset, this.value, this.options.littleEndian);
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/struct/esm/struct.js
var Struct = class {
  constructor(options) {
    __publicField(this, "TFields");
    __publicField(this, "TOmitInitKey");
    __publicField(this, "TExtra");
    __publicField(this, "TInit");
    __publicField(this, "TDeserializeResult");
    __publicField(this, "options");
    __publicField(this, "_size", 0);
    __publicField(this, "_fields", []);
    __publicField(this, "_extra", {});
    __publicField(this, "_postDeserialized");
    __publicField(this, "arrayBufferLike", (name, type, options) => {
      if ("length" in options) {
        return this.field(name, new FixedLengthBufferLikeFieldDefinition(type, options));
      } else {
        return this.field(name, new VariableLengthBufferLikeFieldDefinition(type, options));
      }
    });
    __publicField(this, "uint8Array", (name, options, typeScriptType) => {
      return this.arrayBufferLike(name, Uint8ArrayBufferFieldSubType.Instance, options, typeScriptType);
    });
    __publicField(this, "string", (name, options, typeScriptType) => {
      return this.arrayBufferLike(name, StringBufferFieldSubType.Instance, options, typeScriptType);
    });
    this.options = { ...StructDefaultOptions, ...options };
  }
  /**
   * Gets the static size (exclude fields that can change size at runtime)
   */
  get size() {
    return this._size;
  }
  /**
   * Appends a `StructFieldDefinition` to the `Struct
   */
  field(name, definition) {
    for (const field2 of this._fields) {
      if (field2[0] === name) {
        throw new Error(`This struct already have a field with name '${String(name)}'`);
      }
    }
    this._fields.push([name, definition]);
    const size = definition.getSize();
    this._size += size;
    return this;
  }
  /**
   * Merges (flats) another `Struct`'s fields and extra fields into this one.
   */
  fields(other) {
    for (const field2 of other._fields) {
      this._fields.push(field2);
    }
    this._size += other._size;
    Object.defineProperties(this._extra, Object.getOwnPropertyDescriptors(other._extra));
    return this;
  }
  number(name, type, typeScriptType) {
    return this.field(name, new NumberFieldDefinition(type, typeScriptType));
  }
  /**
   * Appends an `int8` field to the `Struct`
   */
  int8(name, typeScriptType) {
    return this.number(name, NumberFieldType.Int8, typeScriptType);
  }
  /**
   * Appends an `uint8` field to the `Struct`
   */
  uint8(name, typeScriptType) {
    return this.number(name, NumberFieldType.Uint8, typeScriptType);
  }
  /**
   * Appends an `int16` field to the `Struct`
   */
  int16(name, typeScriptType) {
    return this.number(name, NumberFieldType.Int16, typeScriptType);
  }
  /**
   * Appends an `uint16` field to the `Struct`
   */
  uint16(name, typeScriptType) {
    return this.number(name, NumberFieldType.Uint16, typeScriptType);
  }
  /**
   * Appends an `int32` field to the `Struct`
   */
  int32(name, typeScriptType) {
    return this.number(name, NumberFieldType.Int32, typeScriptType);
  }
  /**
   * Appends an `uint32` field to the `Struct`
   */
  uint32(name, typeScriptType) {
    return this.number(name, NumberFieldType.Uint32, typeScriptType);
  }
  bigint(name, type, typeScriptType) {
    return this.field(name, new BigIntFieldDefinition(type, typeScriptType));
  }
  /**
   * Appends an `int64` field to the `Struct`
   *
   * Requires native `BigInt` support
   */
  int64(name, typeScriptType) {
    return this.bigint(name, BigIntFieldType.Int64, typeScriptType);
  }
  /**
   * Appends an `uint64` field to the `Struct`
   *
   * Requires native `BigInt` support
   */
  uint64(name, typeScriptType) {
    return this.bigint(name, BigIntFieldType.Uint64, typeScriptType);
  }
  /**
   * Adds some extra properties into every `Struct` value.
   *
   * Extra properties will not affect serialize or deserialize process.
   *
   * Multiple calls to `extra` will merge all properties together.
   *
   * @param value
   * An object containing properties to be added to the result value. Accessors and methods are also allowed.
   */
  extra(value) {
    Object.defineProperties(this._extra, Object.getOwnPropertyDescriptors(value));
    return this;
  }
  postDeserialize(callback) {
    this._postDeserialized = callback;
    return this;
  }
  deserialize(stream) {
    const structValue = new StructValue(this._extra);
    let promise = SyncPromise.resolve();
    for (const [name, definition] of this._fields) {
      promise = promise.then(() => definition.deserialize(this.options, stream, structValue)).then((fieldValue) => {
        structValue.set(name, fieldValue);
      });
    }
    return promise.then(() => {
      const object = structValue.value;
      if (this._postDeserialized) {
        const override = this._postDeserialized.call(object, object);
        if (override !== void 0) {
          return override;
        }
      }
      return object;
    }).valueOrPromise();
  }
  serialize(init, output) {
    let structValue;
    if (STRUCT_VALUE_SYMBOL in init) {
      structValue = init[STRUCT_VALUE_SYMBOL];
      for (const [key, value] of Object.entries(init)) {
        const fieldValue = structValue.get(key);
        if (fieldValue) {
          fieldValue.set(value);
        }
      }
    } else {
      structValue = new StructValue({});
      for (const [name, definition] of this._fields) {
        const fieldValue = definition.create(this.options, structValue, init[name]);
        structValue.set(name, fieldValue);
      }
    }
    let structSize = 0;
    const fieldsInfo = [];
    for (const [name] of this._fields) {
      const fieldValue = structValue.get(name);
      const size = fieldValue.getSize();
      fieldsInfo.push({ fieldValue, size });
      structSize += size;
    }
    let outputType = "number";
    if (!output) {
      output = new Uint8Array(structSize);
      outputType = "Uint8Array";
    }
    const dataView = new DataView(output.buffer, output.byteOffset, output.byteLength);
    let offset = 0;
    for (const { fieldValue, size } of fieldsInfo) {
      fieldValue.serialize(dataView, offset);
      offset += size;
    }
    if (outputType === "number") {
      return structSize;
    } else {
      return output;
    }
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/stream-extra/esm/wrap-readable.js
function getWrappedReadableStream(wrapper, controller) {
  if ("start" in wrapper) {
    return wrapper.start(controller);
  } else if (typeof wrapper === "function") {
    return wrapper(controller);
  } else {
    return wrapper;
  }
}
var WrapReadableStream = class extends ReadableStream3 {
  constructor(wrapper) {
    super({
      start: async (controller) => {
        await Promise.resolve();
        this.readable = await getWrappedReadableStream(wrapper, controller);
        this.reader = this.readable.getReader();
      },
      cancel: async (reason) => {
        await this.reader.cancel(reason);
        if ("cancel" in wrapper) {
          await wrapper.cancel?.(reason);
        }
      },
      pull: async (controller) => {
        const result = await this.reader.read();
        if (result.done) {
          controller.close();
          if ("close" in wrapper) {
            await wrapper.close?.();
          }
        } else {
          controller.enqueue(result.value);
        }
      }
    });
    __publicField(this, "readable");
    __publicField(this, "reader");
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/stream-extra/esm/duplex.js
var NOOP2 = () => {
};
var DuplexStreamFactory = class {
  constructor(options) {
    __publicField(this, "readableControllers", []);
    __publicField(this, "writers", []);
    __publicField(this, "_writableClosed", false);
    __publicField(this, "_closed", new PromiseResolver2());
    __publicField(this, "options");
    this.options = options ?? {};
  }
  get writableClosed() {
    return this._writableClosed;
  }
  get closed() {
    return this._closed.promise;
  }
  wrapReadable(readable) {
    return new WrapReadableStream({
      start: (controller) => {
        this.readableControllers.push(controller);
        return readable;
      },
      cancel: async () => {
        await this.close();
      },
      close: async () => {
        await this.dispose();
      }
    });
  }
  createWritable(stream) {
    const writer = stream.getWriter();
    this.writers.push(writer);
    return new WritableStream3({
      write: async (chunk) => {
        await writer.write(chunk);
      },
      abort: async (reason) => {
        await writer.abort(reason);
        await this.close();
      },
      close: async () => {
        await writer.close().catch(NOOP2);
        await this.close();
      }
    });
  }
  async close() {
    if (this._writableClosed) {
      return;
    }
    this._writableClosed = true;
    if (await this.options.close?.() !== false) {
      await this.dispose();
    }
    for (const writer of this.writers) {
      await writer.close().catch(NOOP2);
    }
  }
  async dispose() {
    this._writableClosed = true;
    this._closed.resolve();
    for (const controller of this.readableControllers) {
      try {
        controller.close();
      } catch {
      }
    }
    await this.options.dispose?.();
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/stream-extra/esm/pipe-from.js
function pipeFrom(writable, pair) {
  const writer = pair.writable.getWriter();
  const pipe = pair.readable.pipeTo(writable);
  return new WritableStream3({
    async write(chunk) {
      await writer.write(chunk);
    },
    async close() {
      await writer.close();
      await pipe;
    }
  });
}

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/crypto.js
var BigInt0 = BigInt(0);
var BigInt1 = BigInt(1);
var BigInt2 = BigInt(2);
var BigInt64 = BigInt(64);
var RsaPrivateKeyNLength2 = 2048 / 8;
var RsaPrivateKeyDLength2 = 2048 / 8;
var SHA1_DIGEST_LENGTH2 = 20;
var ASN1_SEQUENCE2 = 48;
var ASN1_OCTET_STRING2 = 4;
var ASN1_NULL2 = 5;
var ASN1_OID2 = 6;
var SHA1_DIGEST_INFO2 = new Uint8Array([
  ASN1_SEQUENCE2,
  13 + SHA1_DIGEST_LENGTH2,
  ASN1_SEQUENCE2,
  9,
  // SHA-1 (1 3 14 3 2 26)
  ASN1_OID2,
  5,
  1 * 40 + 3,
  14,
  3,
  2,
  26,
  ASN1_NULL2,
  0,
  ASN1_OCTET_STRING2,
  SHA1_DIGEST_LENGTH2
]);

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/packet.js
var AdbCommand2;
(function(AdbCommand3) {
  AdbCommand3[AdbCommand3["Auth"] = 1213486401] = "Auth";
  AdbCommand3[AdbCommand3["Close"] = 1163086915] = "Close";
  AdbCommand3[AdbCommand3["Connect"] = 1314410051] = "Connect";
  AdbCommand3[AdbCommand3["OK"] = 1497451343] = "OK";
  AdbCommand3[AdbCommand3["Open"] = 1313165391] = "Open";
  AdbCommand3[AdbCommand3["Write"] = 1163154007] = "Write";
})(AdbCommand2 = AdbCommand2 || (AdbCommand2 = {}));
var AdbPacketHeader2 = new Struct({ littleEndian: true }).uint32("command").uint32("arg0").uint32("arg1").uint32("payloadLength").uint32("checksum").int32("magic");
var AdbPacket2 = new Struct({ littleEndian: true }).fields(AdbPacketHeader2).uint8Array("payload", { lengthField: "payloadLength" });
var AdbPacketSerializeStream = class extends ConsumableTransformStream {
  constructor() {
    const headerBuffer = new Uint8Array(AdbPacketHeader2.size);
    super({
      transform: async (chunk, controller) => {
        const init = chunk;
        init.payloadLength = init.payload.byteLength;
        AdbPacketHeader2.serialize(init, headerBuffer);
        await controller.enqueue(headerBuffer);
        if (init.payload.byteLength) {
          await controller.enqueue(init.payload);
        }
      }
    });
  }
};

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/utils/base64.js
var charToIndex2 = [];
var indexToChar2 = [];
var paddingChar2 = "=".charCodeAt(0);
function addRange(start, end) {
  const charCodeStart = start.charCodeAt(0);
  const charCodeEnd = end.charCodeAt(0);
  for (let charCode = charCodeStart; charCode <= charCodeEnd; charCode += 1) {
    charToIndex2[charCode] = indexToChar2.length;
    indexToChar2.push(charCode);
  }
}
addRange("A", "Z");
addRange("a", "z");
addRange("0", "9");
addRange("+", "+");
addRange("/", "/");

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/auth.js
var AdbAuthType2;
(function(AdbAuthType3) {
  AdbAuthType3[AdbAuthType3["Token"] = 1] = "Token";
  AdbAuthType3[AdbAuthType3["Signature"] = 2] = "Signature";
  AdbAuthType3[AdbAuthType3["PublicKey"] = 3] = "PublicKey";
})(AdbAuthType2 = AdbAuthType2 || (AdbAuthType2 = {}));

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/framebuffer.js
var Version2 = new Struct({ littleEndian: true }).uint32("version");
var AdbFrameBufferV12 = new Struct({ littleEndian: true }).uint32("bpp").uint32("size").uint32("width").uint32("height").uint32("red_offset").uint32("red_length").uint32("blue_offset").uint32("blue_length").uint32("green_offset").uint32("green_length").uint32("alpha_offset").uint32("alpha_length").uint8Array("data", { lengthField: "size" });
var AdbFrameBufferV22 = new Struct({ littleEndian: true }).uint32("bpp").uint32("colorSpace").uint32("size").uint32("width").uint32("height").uint32("red_offset").uint32("red_length").uint32("blue_offset").uint32("blue_length").uint32("green_offset").uint32("green_length").uint32("alpha_offset").uint32("alpha_length").uint8Array("data", { lengthField: "size" });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/reverse.js
var AdbReverseStringResponse2 = new Struct().string("length", { length: 4 }).string("content", { lengthField: "length", lengthFieldRadix: 16 });
var AdbReverseError2 = class _AdbReverseError extends Error {
  constructor(message) {
    super(message);
    Object.setPrototypeOf(this, _AdbReverseError.prototype);
  }
};
var AdbReverseNotSupportedError2 = class _AdbReverseNotSupportedError extends Error {
  constructor() {
    super("ADB reverse tunnel is not supported on this device when connected wirelessly.");
    Object.setPrototypeOf(this, _AdbReverseNotSupportedError.prototype);
  }
};
var AdbReverseErrorResponse2 = new Struct().fields(AdbReverseStringResponse2).postDeserialize((value) => {
  if (value.content === "more than one device/emulator") {
    throw new AdbReverseNotSupportedError2();
  } else {
    throw new AdbReverseError2(value.content);
  }
});

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/features.js
var AdbFeature2;
(function(AdbFeature3) {
  AdbFeature3["ShellV2"] = "shell_v2";
  AdbFeature3["Cmd"] = "cmd";
  AdbFeature3["StatV2"] = "stat_v2";
  AdbFeature3["ListV2"] = "ls_v2";
  AdbFeature3["FixedPushMkdir"] = "fixed_push_mkdir";
  AdbFeature3["Abb"] = "abb";
  AdbFeature3["AbbExec"] = "abb_exec";
  AdbFeature3["SendReceiveV2"] = "sendrecv_v2";
})(AdbFeature2 = AdbFeature2 || (AdbFeature2 = {}));

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/subprocess/protocols/shell.js
var AdbShellProtocolId2;
(function(AdbShellProtocolId3) {
  AdbShellProtocolId3[AdbShellProtocolId3["Stdin"] = 0] = "Stdin";
  AdbShellProtocolId3[AdbShellProtocolId3["Stdout"] = 1] = "Stdout";
  AdbShellProtocolId3[AdbShellProtocolId3["Stderr"] = 2] = "Stderr";
  AdbShellProtocolId3[AdbShellProtocolId3["Exit"] = 3] = "Exit";
  AdbShellProtocolId3[AdbShellProtocolId3["CloseStdin"] = 4] = "CloseStdin";
  AdbShellProtocolId3[AdbShellProtocolId3["WindowSizeChange"] = 5] = "WindowSizeChange";
})(AdbShellProtocolId2 = AdbShellProtocolId2 || (AdbShellProtocolId2 = {}));
var AdbShellProtocolPacket2 = new Struct({ littleEndian: true }).uint8("id", placeholder()).uint32("length").uint8Array("data", { lengthField: "length" });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/request.js
var AdbSyncRequestId2;
(function(AdbSyncRequestId3) {
  AdbSyncRequestId3["List"] = "LIST";
  AdbSyncRequestId3["ListV2"] = "LIS2";
  AdbSyncRequestId3["Send"] = "SEND";
  AdbSyncRequestId3["SendV2"] = "SND2";
  AdbSyncRequestId3["Lstat"] = "STAT";
  AdbSyncRequestId3["Stat"] = "STA2";
  AdbSyncRequestId3["LstatV2"] = "LST2";
  AdbSyncRequestId3["Data"] = "DATA";
  AdbSyncRequestId3["Done"] = "DONE";
  AdbSyncRequestId3["Receive"] = "RECV";
})(AdbSyncRequestId2 = AdbSyncRequestId2 || (AdbSyncRequestId2 = {}));
var AdbSyncNumberRequest2 = new Struct({ littleEndian: true }).string("id", { length: 4 }).uint32("arg");
var AdbSyncDataRequest = new Struct({ littleEndian: true }).fields(AdbSyncNumberRequest2).uint8Array("data", { lengthField: "arg" });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/response.js
var AdbSyncResponseId2;
(function(AdbSyncResponseId3) {
  AdbSyncResponseId3["Entry"] = "DENT";
  AdbSyncResponseId3["Entry2"] = "DNT2";
  AdbSyncResponseId3["Lstat"] = "STAT";
  AdbSyncResponseId3["Stat"] = "STA2";
  AdbSyncResponseId3["Lstat2"] = "LST2";
  AdbSyncResponseId3["Done"] = "DONE";
  AdbSyncResponseId3["Data"] = "DATA";
  AdbSyncResponseId3["Ok"] = "OKAY";
  AdbSyncResponseId3["Fail"] = "FAIL";
})(AdbSyncResponseId2 = AdbSyncResponseId2 || (AdbSyncResponseId2 = {}));
var AdbSyncFailResponse2 = new Struct({ littleEndian: true }).uint32("messageLength").string("message", { lengthField: "messageLength" }).postDeserialize((object) => {
  throw new Error(object.message);
});

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/stat.js
var LinuxFileType2;
(function(LinuxFileType3) {
  LinuxFileType3[LinuxFileType3["Directory"] = 4] = "Directory";
  LinuxFileType3[LinuxFileType3["File"] = 8] = "File";
  LinuxFileType3[LinuxFileType3["Link"] = 10] = "Link";
})(LinuxFileType2 = LinuxFileType2 || (LinuxFileType2 = {}));
var AdbSyncLstatResponse2 = new Struct({ littleEndian: true }).int32("mode").int32("size").int32("mtime").extra({
  id: AdbSyncResponseId2.Lstat,
  get type() {
    return this.mode >> 12;
  },
  get permission() {
    return this.mode & 4095;
  }
}).postDeserialize((object) => {
  if (object.mode === 0 && object.size === 0 && object.mtime === 0) {
    throw new Error("lstat error");
  }
});
var AdbSyncStatErrorCode2;
(function(AdbSyncStatErrorCode3) {
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["SUCCESS"] = 0] = "SUCCESS";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EACCES"] = 13] = "EACCES";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EEXIST"] = 17] = "EEXIST";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EFAULT"] = 14] = "EFAULT";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EFBIG"] = 27] = "EFBIG";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EINTR"] = 4] = "EINTR";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EINVAL"] = 22] = "EINVAL";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EIO"] = 5] = "EIO";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EISDIR"] = 21] = "EISDIR";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ELOOP"] = 40] = "ELOOP";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EMFILE"] = 24] = "EMFILE";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENAMETOOLONG"] = 36] = "ENAMETOOLONG";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENFILE"] = 23] = "ENFILE";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENOENT"] = 2] = "ENOENT";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENOMEM"] = 12] = "ENOMEM";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENOSPC"] = 28] = "ENOSPC";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ENOTDIR"] = 20] = "ENOTDIR";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EOVERFLOW"] = 75] = "EOVERFLOW";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EPERM"] = 1] = "EPERM";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["EROFS"] = 30] = "EROFS";
  AdbSyncStatErrorCode3[AdbSyncStatErrorCode3["ETXTBSY"] = 26] = "ETXTBSY";
})(AdbSyncStatErrorCode2 = AdbSyncStatErrorCode2 || (AdbSyncStatErrorCode2 = {}));
var AdbSyncStatResponse2 = new Struct({ littleEndian: true }).uint32("error", placeholder()).uint64("dev").uint64("ino").uint32("mode").uint32("nlink").uint32("uid").uint32("gid").uint64("size").uint64("atime").uint64("mtime").uint64("ctime").extra({
  id: AdbSyncResponseId2.Stat,
  get type() {
    return this.mode >> 12;
  },
  get permission() {
    return this.mode & 4095;
  }
}).postDeserialize((object) => {
  if (object.error) {
    throw new Error(AdbSyncStatErrorCode2[object.error]);
  }
});

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/list.js
var AdbSyncEntryResponse2 = new Struct({ littleEndian: true }).fields(AdbSyncLstatResponse2).uint32("nameLength").string("name", { lengthField: "nameLength" }).extra({ id: AdbSyncResponseId2.Entry });
var AdbSyncEntry2Response2 = new Struct({ littleEndian: true }).fields(AdbSyncStatResponse2).uint32("nameLength").string("name", { lengthField: "nameLength" }).extra({ id: AdbSyncResponseId2.Entry2 });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/pull.js
var AdbSyncDataResponse2 = new Struct({ littleEndian: true }).uint32("dataLength").uint8Array("data", { lengthField: "dataLength" }).extra({ id: AdbSyncResponseId2.Data });

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/commands/sync/push.js
var ADB_SYNC_MAX_PACKET_SIZE2 = 64 * 1024;
var AdbSyncOkResponse2 = new Struct({ littleEndian: true }).uint32("unused");
var AdbSyncSendV2Flags2;
(function(AdbSyncSendV2Flags3) {
  AdbSyncSendV2Flags3[AdbSyncSendV2Flags3["None"] = 0] = "None";
  AdbSyncSendV2Flags3[AdbSyncSendV2Flags3["Brotli"] = 1] = "Brotli";
  AdbSyncSendV2Flags3[AdbSyncSendV2Flags3["Lz4"] = 2] = "Lz4";
  AdbSyncSendV2Flags3[AdbSyncSendV2Flags3["Zstd"] = 4] = "Zstd";
  AdbSyncSendV2Flags3[AdbSyncSendV2Flags3["DryRun"] = 2147483648] = "DryRun";
})(AdbSyncSendV2Flags2 = AdbSyncSendV2Flags2 || (AdbSyncSendV2Flags2 = {}));
var AdbSyncSendV2Request2 = new Struct({ littleEndian: true }).uint32("id", placeholder()).uint32("mode").uint32("flags", placeholder());

// node_modules/@yume-chan/adb-backend-webusb/node_modules/@yume-chan/adb/esm/adb.js
var AdbPropKey;
(function(AdbPropKey2) {
  AdbPropKey2["Product"] = "ro.product.name";
  AdbPropKey2["Model"] = "ro.product.model";
  AdbPropKey2["Device"] = "ro.product.device";
  AdbPropKey2["Features"] = "features";
})(AdbPropKey = AdbPropKey || (AdbPropKey = {}));

// node_modules/@yume-chan/adb-backend-webusb/esm/backend.js
var ADB_DEFAULT_DEVICE_FILTER = {
  classCode: 255,
  subclassCode: 66,
  protocolCode: 1
};
function alternateMatchesFilter(alternate, filters) {
  return filters.some((filter) => alternate.interfaceClass === filter.classCode && alternate.interfaceSubclass === filter.subclassCode && alternate.interfaceProtocol === filter.protocolCode);
}
function findUsbAlternateInterface(device, filters) {
  for (const configuration of device.configurations) {
    for (const interface_ of configuration.interfaces) {
      for (const alternate of interface_.alternates) {
        if (alternateMatchesFilter(alternate, filters)) {
          return { configuration, interface_, alternate };
        }
      }
    }
  }
  throw new Error("No matched alternate interface found");
}
function findUsbEndpoints(endpoints) {
  if (endpoints.length === 0) {
    throw new Error("No endpoints given");
  }
  let inEndpoint;
  let outEndpoint;
  for (const endpoint of endpoints) {
    switch (endpoint.direction) {
      case "in":
        inEndpoint = endpoint;
        if (outEndpoint) {
          return { inEndpoint, outEndpoint };
        }
        break;
      case "out":
        outEndpoint = endpoint;
        if (inEndpoint) {
          return { inEndpoint, outEndpoint };
        }
        break;
    }
  }
  if (!inEndpoint) {
    throw new Error("No input endpoint found.");
  }
  if (!outEndpoint) {
    throw new Error("No output endpoint found.");
  }
  throw new Error("unreachable");
}
var Uint8ArrayStructDeserializeStream = class {
  constructor(buffer2) {
    __publicField(this, "buffer");
    __publicField(this, "offset");
    this.buffer = buffer2;
    this.offset = 0;
  }
  read(length) {
    const result = this.buffer.subarray(this.offset, this.offset + length);
    this.offset += length;
    return result;
  }
};
var AdbWebUsbBackendStream = class {
  constructor(device, inEndpoint, outEndpoint, usbManager) {
    __publicField(this, "_readable");
    __publicField(this, "_writable");
    let closed = false;
    const factory = new DuplexStreamFactory({
      close: async () => {
        try {
          closed = true;
          await device.close();
        } catch {
        }
      },
      dispose: () => {
        usbManager.removeEventListener("disconnect", handleUsbDisconnect);
      }
    });
    function handleUsbDisconnect(e2) {
      if (e2.device === device) {
        factory.dispose().catch((e3) => {
          void e3;
        });
      }
    }
    usbManager.addEventListener("disconnect", handleUsbDisconnect);
    this._readable = factory.wrapReadable(new ReadableStream3({
      async pull(controller) {
        const result = await device.transferIn(inEndpoint.endpointNumber, 24);
        const buffer2 = new Uint8Array(result.data.buffer);
        const stream = new Uint8ArrayStructDeserializeStream(buffer2);
        const packet = AdbPacketHeader2.deserialize(stream);
        if (packet.payloadLength !== 0) {
          const result2 = await device.transferIn(inEndpoint.endpointNumber, packet.payloadLength);
          packet.payload = new Uint8Array(result2.data.buffer);
        } else {
          packet.payload = EMPTY_UINT8_ARRAY;
        }
        controller.enqueue(packet);
      }
    }));
    const zeroMask = outEndpoint.packetSize - 1;
    this._writable = pipeFrom(factory.createWritable(new ConsumableWritableStream2({
      write: async (chunk) => {
        try {
          await device.transferOut(outEndpoint.endpointNumber, chunk);
          if (zeroMask && (chunk.byteLength & zeroMask) === 0) {
            await device.transferOut(outEndpoint.endpointNumber, EMPTY_UINT8_ARRAY);
          }
        } catch (e2) {
          if (closed) {
            return;
          }
          throw e2;
        }
      }
    })), new AdbPacketSerializeStream());
  }
  get readable() {
    return this._readable;
  }
  get writable() {
    return this._writable;
  }
};
var AdbWebUsbBackend = class {
  /**
   * Create a new instance of `AdbWebBackend` using a specified `USBDevice` instance
   *
   * @param device The `USBDevice` instance obtained elsewhere.
   * @param filters The filters to use when searching for ADB interface. Defaults to {@link ADB_DEFAULT_DEVICE_FILTER}.
   */
  constructor(device, filters = [ADB_DEFAULT_DEVICE_FILTER], usb) {
    __publicField(this, "_filters");
    __publicField(this, "_usb");
    __publicField(this, "_device");
    this._device = device;
    this._filters = filters;
    this._usb = usb;
  }
  get device() {
    return this._device;
  }
  get serial() {
    return this._device.serialNumber;
  }
  get name() {
    return this._device.productName;
  }
  /**
   * Claim the device and create a pair of `AdbPacket` streams to the ADB interface.
   * @returns The pair of `AdbPacket` streams.
   */
  async connect() {
    if (!this._device.opened) {
      await this._device.open();
    }
    const { configuration, interface_, alternate } = findUsbAlternateInterface(this._device, this._filters);
    if (this._device.configuration?.configurationValue !== configuration.configurationValue) {
      await this._device.selectConfiguration(configuration.configurationValue);
    }
    if (!interface_.claimed) {
      await this._device.claimInterface(interface_.interfaceNumber);
    }
    if (interface_.alternate.alternateSetting !== alternate.alternateSetting) {
      await this._device.selectAlternateInterface(interface_.interfaceNumber, alternate.alternateSetting);
    }
    const { inEndpoint, outEndpoint } = findUsbEndpoints(alternate.endpoints);
    return new AdbWebUsbBackendStream(this._device, inEndpoint, outEndpoint, this._usb);
  }
};

// node_modules/@yume-chan/adb-backend-webusb/esm/manager.js
var _AdbWebUsbBackendManager = class _AdbWebUsbBackendManager {
  /**
   * Create a new instance of `AdbWebUsbBackendManager` using the specified WebUSB API implementation.
   * @param usb A WebUSB compatible interface.
   */
  constructor(usb) {
    __publicField(this, "_usb");
    this._usb = usb;
  }
  /**
   * Request access to a connected device.
   * This is a convince method for `usb.requestDevice()`.
   * @param filters
   * The filters to apply to the device list.
   *
   * It must have `classCode`, `subclassCode` and `protocolCode` fields for selecting the ADB interface,
   * but might also have `vendorId`, `productId` or `serialNumber` fields to limit the displayed device list.
   *
   * Defaults to {@link ADB_DEFAULT_DEVICE_FILTER}.
   * @param usbManager
   * A WebUSB compatible interface.
   * For example, `usb` NPM package for Node.js has a `webusb` object that can be used here.
   *
   * Defaults to `window.navigator.usb` (will throw an error if not exist).
   * @returns The `AdbWebUsbBackend` instance if the user selected a device,
   * or `undefined` if the user cancelled the device picker.
   */
  async requestDevice(filters = [ADB_DEFAULT_DEVICE_FILTER]) {
    try {
      const device = await this._usb.requestDevice({
        filters
      });
      return new AdbWebUsbBackend(device, filters, this._usb);
    } catch (e2) {
      if (typeof e2 === "object" && e2 !== null && "name" in e2 && e2.name === "NotFoundError") {
        return void 0;
      }
      throw e2;
    }
  }
  /**
   * Get all connected and authenticated devices.
   * This is a convince method for `usb.getDevices()`.
   * @param filters
   * The filters to apply to the device list.
   *
   * It must have `classCode`, `subclassCode` and `protocolCode` fields for selecting the ADB interface,
   * but might also have `vendorId`, `productId` or `serialNumber` fields to limit the displayed device list.
   *
   * Defaults to {@link ADB_DEFAULT_DEVICE_FILTER}.
   * @param usbManager
   * A WebUSB compatible interface.
   * For example, `usb` NPM package for Node.js has a `webusb` object that can be used here.
   *
   * Defaults to `window.navigator.usb` (will throw an error if not exist).
   * @returns An array of `AdbWebUsbBackend` instances for all connected and authenticated devices.
   */
  async getDevices(filters = [ADB_DEFAULT_DEVICE_FILTER]) {
    const devices = await this._usb.getDevices();
    return devices.map((device) => new AdbWebUsbBackend(device, filters, this._usb));
  }
};
/**
 * Gets the instance of AdbWebUsbBackendManager using browser WebUSB implementation.
 *
 * May be `undefined` if the browser does not support WebUSB.
 */
__publicField(_AdbWebUsbBackendManager, "BROWSER", typeof window !== "undefined" && !!window.navigator.usb ? new _AdbWebUsbBackendManager(window.navigator.usb) : void 0);
var AdbWebUsbBackendManager = _AdbWebUsbBackendManager;
export {
  ADB_DEFAULT_AUTHENTICATORS,
  ADB_DEFAULT_DEVICE_FILTER,
  Adb,
  AdbAuthenticationProcessor,
  AdbDaemonTransport,
  AdbPublicKeyAuthenticator,
  AdbSignatureAuthenticator,
  AdbWebUsbBackend
};
/*! Bundled license information:

web-streams-polyfill/dist/ponyfill.mjs:
  (**
   * @license
   * web-streams-polyfill v4.3.0
   * Copyright 2026 Mattias Buelens, Diwank Singh Tomer and other contributors.
   * This code is released under the MIT license.
   * SPDX-License-Identifier: MIT
   *)
*/
