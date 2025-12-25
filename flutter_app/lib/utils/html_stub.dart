// Stub file for mobile platforms
// This file is only used when dart:html is not available
// It provides empty classes to satisfy the compiler

class Blob {
  Blob(List<dynamic> blobParts, [String? type, String? endings]);
}

class Url {
  static String createObjectUrlFromBlob(Blob blob) => '';
  static void revokeObjectUrl(String url) {}
}

class AnchorElement {
  String? href;
  AnchorElement({this.href});
  void setAttribute(String name, String value) {}
  void click() {}
}

class FileReader {
  dynamic result;
  Stream get onLoad => const Stream.empty();
  void readAsArrayBuffer(dynamic file) {}
}

class File {
  String name;
  File(this.name);
}

