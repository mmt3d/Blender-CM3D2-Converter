from unittest import TestCase
import CM3D2.Serialization  # type: ignore
import CM3D2.Serialization.Files  # type: ignore
import cm3d2converter
from System.IO import MemoryStream  # type: ignore


class TestCM3D2Serialization(TestCase):

    def test_serializer(self):
        serializer = CM3D2.Serialization.CM3D2Serializer()
        stream = MemoryStream()
        anm = CM3D2.Serialization.Files.Anm()
        serializer.Serialize(stream, anm)
        string = ""
        for byte in stream.GetBuffer():
            byte: int
            string += hex(byte)[2:] + " "
        print(string)
