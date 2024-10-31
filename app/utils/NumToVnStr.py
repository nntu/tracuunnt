
class NumToVnStr:
    def __init__(self, mươi='mươi', nghìn='nghìn', tư='tư', lăm='lăm', linh='linh', tỷ='tỷ', đọc_số_rỗng=True):
        self.chữ_số = ('không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín', 'mười')
        self.mươi = mươi
        self.trăm = 'trăm'
        self.nghìn = nghìn
        self.triệu = 'triệu'
        self.tỷ = tỷ
        self.mốt = 'mốt'
        self.tư = tư
        self.lăm = lăm
        self.linh = linh
        self.đọc_số_rỗng = đọc_số_rỗng
    def to_vn_str(self, s):
        return self._arbitrary(s.lstrip('0'))
    def _int(self, c):
        return ord(c) - ord('0') if c else 0
    def _LT1e2(self, s):
        if len(s) <= 1: return self.chữ_số[self._int(s)]
        if s[0] == '1':
            ret = self.chữ_số[10]
        else:
            ret = self.chữ_số[self._int(s[0])]
            if self.mươi: ret += ' ' + self.mươi
            elif s[1] == '0': ret += ' mươi'
        if s[1] != '0':
            ret += ' '
            if   s[1] == '1' and s[0] != '1': ret += self.mốt
            elif s[1] == '4' and s[0] != '1': ret += self.tư
            elif s[1] == '5': ret += self.lăm
            else: ret += self.chữ_số[self._int(s[1])]
        return ret
    def _LT1e3(self, s):
        if len(s) <= 2: return self._LT1e2(s)
        if s == '000': return ''
        ret = self.chữ_số[self._int(s[0])] + ' ' + self.trăm
        if s[1] != '0':
            ret += ' ' + self._LT1e2(s[1:])
        elif s[2] != '0':
            ret += ' ' + self.linh + ' ' + self.chữ_số[self._int(s[2])]
        return ret
    def _LT1e9(self, s):
        if len(s) <= 3: return self._LT1e3(s)
        if s == '000000' or s == '000000000': return ''
        mid = len(s) % 3 if len(s) % 3 else 3
        left, right = self._LT1e3(s[:mid]), self._LT1e9(s[mid:])
        hang = self.nghìn if len(s) <= 6 else self.triệu
        if not left:
            if not self.đọc_số_rỗng: return right
            else: return self.chữ_số[0] + ' ' + hang + ' ' + right
        if not right: return left + ' ' + hang
        return left + ' ' + hang + ' ' + right
    def _arbitrary(self, s):
        if len(s) <= 9: return self._LT1e9(s)
        mid = len(s) % 9 if len(s) % 9 else 9
        left, right = self._LT1e9(s[:mid]), self._arbitrary(s[mid:])
        hang = ' '.join([self.tỷ] * ((len(s) - mid) // 9))
        if not left:
            if not self.đọc_số_rỗng: return right
            elif right: return self.chữ_số[0] + ' ' + hang + ', ' + right
            else: return right
        if not right: return left + ' ' + hang
        return left + ' ' + hang + ', ' + right
