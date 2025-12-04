class FilterPipeline:
    def __init__(self, filters):
        self.filters = filters

    def run(self, qs, params):
        for f in self.filters:
            qs = f.apply(qs, params)
        return qs