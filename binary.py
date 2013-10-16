from struct import pack, unpack, calcsize
from collections import OrderedDict

def getbytes(s, n):
    b = s.read(n)
    assert len(b) == n, "Unexpected EOF"
    return b

def getbyte(s):
    return getbytes(s, 1)

class Seek(object):
    def __init__(self, s, *args, **kwargs):
        self.old_pos = None
        self.s = s
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        self.old_pos = self.s.tell()
        self.s.seek(*self.args, **self.kwargs)

    def __exit__(self, exc_type, exc_value, traceback):
        self.s.seek(self.old_pos)

class FakeWriteStream(object):
    def __init__(self, offset):
        self.offset = offset

    def seek(self, offset):
        self.offset = offset

    def tell(self):
        return self.offset

    def write(self, data):
        self.offset += len(data)

class BaseField(object):
    def unpack(self, s):
        self.data = self.unpack_data(s)

    def unpack_data(self, s):
        raise notImplementedError

    def pack(self, s):
        self.pack_data(s, self.data)

    def pack_data(self, s, data):
        raise NotImplementedError

    def full_pack(self, s):
        new_data = self.data
        while True:
            old_data = new_data
            self.pack(FakeWriteStream(s.tell()))
            new_data = self.data
            if old_data == new_data:
                break
        self.pack(s)

    def serialize(self):
        return self.data

class Struct(BaseField):
    def add_field(self, name, f):
        assert name not in self.field, name
        self.field[name] = f
        input_type, v = self.input
        if input_type == "data":
            f.data = v.get(name, None)
        elif input_type == "stream":
            f.unpack(v)
        else:
            assert False, input_type
        return f

    def F(self, name, f):
        return self.add_field(name, f)

    def unpack(self, s):
        self.field = OrderedDict()
        self.input = ("stream", s)
        self.fields()
        del self.input

    def pack(self, s):
        for name, f in self.field.iteritems():
            f.pack(s)

    @property
    def data(self):
        data = OrderedDict()
        for k, v in self.field.iteritems():
            data[k] = v.data
        return data

    @data.setter
    def data(self, v):
        self.field = OrderedDict()
        self.input = ("data", v)
        self.fields()
        del self.input

    def serialize(self):
        data = OrderedDict()
        for k, v in self.field.iteritems():
            data[k] = v.serialize()
        return data


    def fields(self):
        raise NotImplementedError

class Magic(BaseField):
    def __init__(self, magic):
        self.magic = magic

    def unpack(self, s):
        data = getbytes(s, len(self.magic))
        assert data == self.magic

    def pack(self, s):
        s.write(self.magic)

    @property
    def data(self):
        return self.magic

    @data.setter
    def data(self, v):
        assert v == self.magic or v is None, v

class Format(BaseField):
    def __init__(self, fmt):
        if fmt[0] in "@=<>!":
            bosa = fmt[0]
            fmt = fmt[1:]
        else:
            bosa = "<"
        self.bosa = bosa
        self.fmt = fmt
        self.single = len(fmt) == 1

    def unpack_data(self, s):
        fmt = self.bosa + self.fmt
        size = calcsize(fmt)
        b = getbytes(s, size)
        data = unpack(fmt, b)
        if self.single:
            assert len(data) == 1
            data = data[0]
        return data

    def pack_data(self, s, data):
        if self.single:
            data = (data,)
        s.write(pack(self.fmt, *data))

class BaseArray(BaseField):
    def __init__(self, field_maker=None, field_function=None):
        if field_function is None:
            field_function = lambda i, f: field_maker()
        self.field_fun = field_function

    def unpack(self, s):
        self.field = [self.field_fun(i, self) for i in xrange(self.size)]
        for f in self.field:
            f.unpack(s)

    def pack(self, s):
        for f in self.field:
            f.pack(s)

    @property
    def data(self):
        return [f.data for f in self.field]

    @data.setter
    def data(self, v):
        self.field = [self.field_fun(i, self) for i in xrange(len(v))]
        for f, fv in zip(self.field, v):
            f.data = fv

    def serialize(self):
        return [f.serialize() for f in self.field]

class Array(BaseArray):
    def __init__(self, size, *args, **kwargs):
        self.size = size
        BaseArray.__init__(self, *args, **kwargs)

class PrefixedArray(BaseArray):
    def __init__(self, prefix_field, *args, **kwargs):
        self.prefix_field = prefix_field
        BaseArray.__init__(self, *args, **kwargs)

    @property
    def size(self):
        return self.prefix_field.data

    def unpack(self, s):
        self.prefix_field.unpack(s)
        BaseArray.unpack(self, s)

    def pack(self, s):
        self.prefix_field.data = len(self.field)
        self.prefix_field.pack(s)
        BaseArray.pack(self, s)

class BaseBlob(BaseField):
    def unpack_data(self, s):
        return getbytes(s, self.size)

    def pack_data(self, s, data):
        s.write(data)

class Blob(BaseBlob):
    def __init__(self, size):
        self.size = size

class PrefixedBlob(BaseBlob):
    def __init__(self, prefix_field, *args, **kwargs):
        self.prefix_field = prefix_field
        BaseBlob.__init__(self, *args, **kwargs)

    @property
    def size(self):
        return self.prefix_field.data

    def unpack(self, s):
        self.prefix_field.unpack(s)
        BaseBlob.unpack(self, s)

    def pack(self, s):
        self.prefix_field.data = len(self.field)
        self.prefix_field.pack(s)
        BaseBlob.pack(self, s)

class String(BaseField):
    def unpack_data(self, s):
        lc = []
        c = getbyte(s)
        while c != "\0":
            lc.append(c)
            c = getbyte(s)
        return "".join(lc)

    def pack_data(self, s, data):
        s.write(data)
        s.write('\0')

class FixedString(BaseField):
    def __init__(self, size):
        self.size = size

    def unpack_data(self, s):
        data = getbytes(s, self.size)
        data = data.rstrip("\0")
        return data

    def pack_data(self, s, data):
        data = data.ljust(self.size, "\0")
        s.write(data)

class Index(BaseField):
    def __init__(self, array, index_field):
        self.array = array
        self.index_field = index_field

    def unpack_data(self, s):
        self.index_field.unpack(s)
        return self.array.field[self.index_field.data].data

    def pack_data(self, s, data):
        if data not in self.array.data:
            self.array.data = self.array.data + [data]
        self.index_field.data = self.array.data.index(data)
        self.index_field.pack(s)

class Offset(BaseField):
    def unpack_data(self, s):
        return s.tell()

    def pack_data(self, s, data):
        self.data = s.tell()

class Pointer(BaseField):
    def __init__(self, offset, field):
        self.offset = offset
        self.field = field

    def unpack(self, s):
        with Seek(s, self.offset):
            self.field.unpack(s)

    @property
    def data(self):
        return self.field.data

    @data.setter
    def data(self, v):
        self.field.data = v
