# -*- coding: utf-8 -*-
from contextlib import closing
from fs.base import FS
from fs.info import Info
from fs import errors
from fs.enums import ResourceType
from io import BytesIO
from pcloud.api import PyCloud


class PCloudFile(BytesIO):
    """ A file representation for pCloud files
    """
    def __init__(self, pcloud, path, mode):
        self.pcloud = pcloud
        self.path = path
        self.mode = mode
        initial_data = None
        self.rev = None
        try:
            response = self.pcloud.downloadfile(path=self.path)
            with closing(response):
                if self.mode.reading and not self.mode.truncate:
                    initial_data = response.content
        except Exception:
            # if the file doesn't exist, we don't need to read it's initial state
            pass
        super().__init__(initial_data)
        if self.mode.appending and initial_data is not None:
            # seek to the end
            self.seek(len(initial_data))

    def close(self):
        if not self.mode.writing:
            return
        metadata = self.pcloud.uploadfile(self.getvalue(), self.path, mode=writeMode, autorename=False, client_modified=datetime.utcnow(), mute=False)
        # Make sure that we can't call this again
        self.path = None
        self.mode = None
        self.pcloud = None


class PCloudFS(FS):
    """ A Python virtual filesystem representation for pCloud """

    def __init__(self, username, password):
        super().__init__()
        self.pcloud = PyCloud(username, password)
        self._meta = {
            "case_insensitive": False,
            "invalid_path_chars": ":",  # not sure what else
            "max_path_length": None,  # don't know what the limit is
            "max_sys_path_length": None,  # there's no syspath
            "network": True,
            "read_only": False,
            "supports_rename": False  # since we don't have a syspath...
        }

    def __repr__(self):
        return "<pCloudFS>"

    def _info_from_metadata(self, metadata, namespaces):
        info = {
            'basic': {
                'is_dir': metadata.get('isfolder', False),
                'name': metadata.get('name')
            }
        }
        if 'details' in namespaces:
            info['details'] = {
                'type': 1 if metadata.get('isfolder') else 2,
                'accessed': None,
                'modified': metadata.get('modified'),
                'created': metadata.get('created'),
                'metadata_changed': metadata.get('modified'),
                'size': metadata.get('size', 0)
            }
        if 'link' in namespaces:
            pass
        if 'access' in namespaces:
            pass
        return Info(info)

    def getinfo(self, path, namespaces=None):
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path)
        # we strip the last item from the path to get
        # the parent folder. since the pCloud API
        # provides no consistent way of geting the metadata
        # for both folders and files we extract it from the
        # folder listing
        if path == '/':
            parent_path = '/'
        else:
            parent_path = '/'.join(_path.split('/')[:-1])
            parent_path = parent_path if parent_path else '/'
        try:
            folder_list = self.pcloud.listfolder(path=parent_path)
            if _path == '/':
                metadata = folder_list['metadata']
            else:
                for item in folder_list['metadata']['contents']:
                    if item['path'] == _path:
                        metadata = item
                        break
        except Exception as e:
            raise errors.ResourceNotFound(path=path, exc=e)
        return self._info_from_metadata(metadata, namespaces)

    def setinfo(self, path, info):  # pylint: disable=too-many-branches
        # pCloud doesn't support changing any of the metadata values
        pass

    def listdir(self, path):
        _path = self.validatepath(path)

        _type = self.gettype(_path)
        if _type is not ResourceType.directory:
            raise errors.DirectoryExpected(path)
        result = self.pcloud.listfolder(path=_path)
        return [item['name'] for item in result['metadata']['contents']]

    def makedir(self, path, permissions=None, recreate=False):
        self.check()
        self.pcloud.createfolder(path=path)

    def openbin(self, path, mode="r", buffering=-1, **options):
        pass
        # XXX

    def remove(self, path):
        self.pcloud.deletefile(path=path)

    def removedir(self, path):
        self.pcloud.deletefolder(path=path)

    def removetree(self, dir_path):
        self.pcloud.deletefolderrecursive(path=dir_path)

# EOF
