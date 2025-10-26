class SynthesisError(Exception):
    def __init__(self, msg, raw=None):
        super().__init__(msg)
        self.raw = raw
