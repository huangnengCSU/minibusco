import os
import hashlib
import tarfile
import shutil
import urllib.request
from utils import Error


class URLError(OSError):
    # URLError is a sub-type of OSError, but it doesn't share any of
    # the implementation.  need to override __init__ and __str__.
    # It sets self.args for compatibility with other OSError
    # subclasses, but args doesn't have the typical format with errno in
    # slot 0 and strerror in slot 1.  This may be better than nothing.
    def __init__(self, reason, filename=None):
        self.args = reason,
        self.reason = reason
        if filename is not None:
            self.filename = filename

    def __str__(self):
        return '<urlopen error %s>' % self.reason


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class Downloader:
    def __init__(self, download_dir=None):
        self.base_url = "https://busco-data.ezlab.org/v5/data/"
        self.default_lineage = ["archaea_odb10", "bacteria_odb10", "eukaryota_odb10"]
        if download_dir is None:
            self.download_dir = "downloads"
        else:
            self.download_dir = download_dir
        if not os.path.exists(self.download_dir):
            os.mkdir(self.download_dir)
        self.lineage_description = self.download_file_version_document()
        for lineage in self.default_lineage:
            try:
                expected_hash = self.lineage_description[lineage][1]
                if os.path.exists(os.path.join(self.download_dir, "{}/refseq_db.faa.gz".format(lineage))):
                    observed_hash = md5(os.path.join(self.download_dir, "{}/refseq_db.faa.gz".format(lineage)))
                    if expected_hash == observed_hash:
                        self.lineage_description[lineage].append(
                            os.path.join(self.download_dir, "{}/refseq_db.faa.gz".format(lineage)))
                    else:
                        print("md5 hash is incorrect: {} while {} expected".format(str(observed_hash),
                                                                                   str(expected_hash)))
                        shutil.rmtree(os.path.join(self.download_dir, lineage))
                        os.remove(os.path.join(self.download_dir, "{}/refseq_db.faa.gz".format(lineage)))
                else:
                    self.download_lineage(lineage)
            except KeyError:
                raise Error("invalid lineage name: {}".format(lineage))

    @staticmethod
    def download_single_file(remote_filepath, local_filepath, expected_hash):
        try:
            urllib.request.urlretrieve(remote_filepath, local_filepath)
            observed_hash = md5(local_filepath)
            if observed_hash != expected_hash:
                print("md5 hash is incorrect: {} while {} expected".format(str(observed_hash), str(expected_hash)))
                print("deleting corrupted file {}".format(local_filepath))
                os.remove(local_filepath)
                raise Error("Unable to download necessary files")
            else:
                print("Success download from {}".format(remote_filepath))
                print("md5 hash is {}".format(observed_hash))
        except URLError:
            print("Cannot reach {}".format(remote_filepath))
            return False
        return True

    def download_file_version_document(self):
        file_version_url = self.base_url + "file_versions.tsv"
        file_version_download_path = os.path.join(self.download_dir, "file_versions.tsv")
        hash_url = self.base_url + "file_versions.tsv.hash"
        hash_download_path = os.path.join(self.download_dir, "file_versions.tsv.hash")

        ## download hash file
        try:
            urllib.request.urlretrieve(hash_url, hash_download_path)
        except URLError:
            print("Cannot reach {}".format(hash_url))
            raise Error("Unable to download necessary files")
        expected_file_version_hash = ""
        with open(hash_download_path, 'r') as fin:
            expected_file_version_hash = fin.readline().strip()

        ## download file version
        download_success = self.download_single_file(file_version_url, file_version_download_path,
                                                     expected_file_version_hash)
        lineages_description_dict = {}
        if download_success:
            with open(file_version_download_path, 'r') as fin:
                for line in fin:
                    strain, date, hash_value, category, info = line.strip().split()
                    if info != "lineages":
                        continue
                    lineages_description_dict[strain] = [date, hash_value, category]
            return lineages_description_dict
        else:
            return None

    def download_lineage(self, lineage=None):
        if lineage is None:
            lineages = self.default_lineage
        else:
            lineages = [lineage]
        for lineage in lineages:
            date, expected_hash = self.lineage_description[lineage][0:2]  # [date, hash_value, category]
            remote_url = self.base_url + "lineages/{}.{}.tar.gz".format(lineage, date)
            download_path = os.path.join(self.download_dir, "{}.{}.tar.gz".format(lineage, date))
            download_success = self.download_single_file(remote_url, download_path, expected_hash)
            if download_success:
                tar = tarfile.open(download_path)
                tar.extractall(self.download_dir)
                tar.close()
                print("Gene library extraction finished")
                print("Gene library ready!\n Reference file: {}/{}/refseq_db.faa.gz".format(self.download_dir, lineage))
                local_lineage_dir = "{}/{}".format(self.download_dir, lineage)
                self.lineage_description[lineage].append(local_lineage_dir)

    def has_local_lineage(self, lineage):
        try:
            if len(self.lineage_description[lineage]) == 4:
                return True
            else:
                return False
        except KeyError:
            raise Error("invalid lineage name: {}".format(lineage))


if __name__ == "__main__":
    d = Downloader()
    d.download_lineage("thiotrichales_odb10")
    d.download_lineage("tunavirinae")
    for k in d.lineage_description:
        print(k)
        print(d.lineage_description[k])
