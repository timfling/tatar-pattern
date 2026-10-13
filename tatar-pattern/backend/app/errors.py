class APIError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status = status
        self.payload = {'error': {'code': code, 'message': message}}
        if details is not None:
            self.payload['error']['details'] = details
