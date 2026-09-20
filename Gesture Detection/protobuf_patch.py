import os
import google.protobuf.message_factory
import google.protobuf.symbol_database
import google.protobuf.descriptor

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['GLOG_minloglevel'] = '2'

def _get_field_label(self):
    if hasattr(self, '_label') and self._label is not None:
        return self._label
    if getattr(self, 'is_repeated', False):
        return 3  # LABEL_REPEATED
    if getattr(self, 'is_required', False):
        return 2  # LABEL_REQUIRED
    return 1  # LABEL_OPTIONAL

# Patch Protobuf 5.x+ / 7.x compatibility with MediaPipe 0.10.x
if not hasattr(google.protobuf.message_factory.MessageFactory, 'GetPrototype'):
    google.protobuf.message_factory.MessageFactory.GetPrototype = (
        lambda self, descriptor: google.protobuf.message_factory.GetMessageClass(descriptor)
    )

if not hasattr(google.protobuf.symbol_database.SymbolDatabase, 'GetPrototype'):
    google.protobuf.symbol_database.SymbolDatabase.GetPrototype = (
        lambda self, descriptor: google.protobuf.message_factory.GetMessageClass(descriptor)
    )

try:
    import google._upb._message
    if not hasattr(google._upb._message.FieldDescriptor, 'label'):
        google._upb._message.FieldDescriptor.label = property(_get_field_label)
except ImportError:
    pass

if not hasattr(google.protobuf.descriptor.FieldDescriptor, 'label'):
    google.protobuf.descriptor.FieldDescriptor.label = property(_get_field_label)

