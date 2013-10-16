from binary import Struct, Magic, Format, String, Blob, PrefixedBlob, PrefixedArray, Array, Index, FixedString, BaseField
import json
from uuid import UUID, uuid4

class UUIDField(Blob):
    def __init__(self):
        Blob.__init__(self, 16)

    def unpack_data(self, s):
        data = Blob.unpack_data(self, s)
        return UUID(bytes=data).urn

    def pack_data(self, s, data):
        Blob.pack_data(self, s, UUID(data).bytes)

class ElementIndex(BaseField):
    def __init__(self, elements, attributes, index_field):
        self.elements = elements
        self.attributes = attributes
        self.index_field = index_field

    def unpack_data(self, s):
        self.index_field.unpack(s)
        return self.elements.field[self.index_field.data]

    def pack_data(self, s, data):
        try:
            index = self.elements.field.index(data)
        except ValueError:
            data.new_guid()
            index = len(self.elements.field)
            self.elements.append_data(data.data)
            self.attributes.append_data(data.attribute.data)
            self.elements.field[index].attribute = self.attributes.field[index]
        self.index_field.data = index
        self.index_field.pack(s)

    def serialize(self):
        return self.index_field.data

class Attribute(Struct):
    def __init__(self, namefield, stringfield, elementindexfield):
        self.namefield = namefield
        self.stringfield = stringfield
        self.elementindexfield = elementindexfield

    def fields(self):
        self.F("name", self.namefield())
        type = self.F("type", Format("B")).data

        attribute_types = {
            1 : self.elementindexfield, # element index
            2 : lambda: Format("I"), # integer
            3 : lambda: Format("f"), # float
            4 : lambda: Format("?"), # bool
            5 : self.stringfield, # string
            6 : lambda: PrefixedBlob(Format("I")), # blob
            7 : lambda: Format("I"), # time
            8 : lambda: Format("4B"), # color
            9 : lambda: Format("2f"), # vector2
            10 : lambda: Format("3f"), # vector3
            11 : lambda: Format("4f"), # vector4
            12 : lambda: Format("3f"), # angle
            13 : lambda: Format("4f"), # quaternion
            14 : lambda: Format("16f"), # matrix
        }

        if 1 <= type <= 14:
            self.F("data", attribute_types[type]())
        elif 14 < type <= 28:
            self.F("data", PrefixedArray(Format("I"), attribute_types[type - 14]))
        else:
            assert False, type

class Element(Struct):
    def __init__(self, namefield, stringfield):
        self.namefield = namefield
        self.stringfield = stringfield

    def fields(self):
        self.F("type", self.namefield())
        self.F("name", self.stringfield())
        self.F("guid", UUIDField())

    def __eq__(self, other):
        return isinstance(other, Element) and self.field["guid"].data == other.field["guid"].data

    def new_guid(self):
        self.field["guid"].data = uuid4().urn

class PCF(Struct):
    def __init__(self, include_attributes=True):
        self.include_attributes = include_attributes

    def fields(self):
        self.F("magic", Magic("<!-- dmx encoding "))
        self.F("version", FixedString(len("binary 2 format pcf 1")))
        self.F("magic2", Magic(" -->\n\0"))
        version = self.field["version"].data
        assert version in ["binary 2 format pcf 1", "binary 5 format pcf 2"], version

        if version == "binary 2 format pcf 1":
            prefix = Format("h")
        else:
            prefix = Format("I")
        strings = self.F("strings", PrefixedArray(prefix, String))

        if version == "binary 2 format pcf 1":
            namefield = lambda: Index(strings, Format("h"))
            stringfield = String
        else:
            namefield = lambda: Index(strings, Format("I"))
            stringfield = namefield
        self.F("elements", PrefixedArray(Format("I"), lambda: Element(namefield, stringfield)))
        if self.include_attributes:
            self.F("attributes",
                Array(len(self.field["elements"].field),
                    field_function=lambda i, f: PrefixedArray(
                        Format("I"),
                        lambda: Attribute(
                            namefield,
                            stringfield,
                            lambda: ElementIndex(self.field["elements"], f, Format("I"))))))
            for i in xrange(len(self.field["elements"].field)):
                self.field["elements"].field[i].attribute = self.field["attributes"].field[i]

    def minimize(self):
        self.field["strings"].data = []
        self.field["elements"].data = [self.field["elements"].data[0]]
        self.field["attributes"].data = [self.field["attributes"].data[0]]
        self.field["elements"].field[0].attribute = self.field["attributes"].field[0]
