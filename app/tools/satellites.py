""" Module for download satellites from internet ("flysat.com")
    for  replace or update current satellites.xml file.
"""
import re

import requests
from enum import Enum
from html.parser import HTMLParser

from app.commons import log
from app.eparser import Satellite, Transponder, is_transponder_valid
from app.eparser.ecommons import PLS_MODE


class SatelliteSource(Enum):
    FLYSAT = ("https://www.flysat.com/satlist.php",)
    LYNGSAT = ("https://www.lyngsat.com/asia.html", "https://www.lyngsat.com/europe.html",
               "https://www.lyngsat.com/atlantic.html", "https://www.lyngsat.com/america.html")

    @staticmethod
    def get_sources(src):
        return src.value


class SatellitesParser(HTMLParser):
    """ Parser for satellite html page. """

    _HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:45.0) Gecko/20100101 Firefox/59.02"}

    def __init__(self, source=SatelliteSource.FLYSAT, entities=False, separator=' '):

        HTMLParser.__init__(self)

        self._parse_html_entities = entities
        self._separator = separator
        self._is_td = False
        self._is_th = False
        self._is_provider = False
        self._current_row = []
        self._current_cell = []
        self._rows = []
        self._source = source

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self._is_td = True
        if tag == 'tr':
            self._is_th = True
        if tag == "a":
            self._current_row.append(attrs[0][1])

    def handle_data(self, data):
        """ Save content to a cell """
        if self._is_td or self._is_th:
            self._current_cell.append(data.strip())

    def handle_endtag(self, tag):
        if tag == 'td':
            self._is_td = False
        elif tag == 'tr':
            self._is_th = False

        if tag in ('td', 'th'):
            final_cell = self._separator.join(self._current_cell).strip()
            self._current_row.append(final_cell)
            self._current_cell = []
        elif tag == 'tr':
            row = self._current_row
            self._rows.append(row)
            self._current_row = []

    def error(self, message):
        pass

    def get_satellites_list(self, source):
        """ Getting complete list of satellites. """
        self.reset()
        self._rows.clear()
        self._source = source

        for src in SatelliteSource.get_sources(self._source):
            try:
                request = requests.get(url=src, headers=self._HEADERS)
            except requests.exceptions.ConnectionError as e:
                log(repr(e))
                return []
            else:
                reason = request.reason
                if reason == "OK":
                    self.feed(request.text)
                else:
                    log(reason)

        if self._rows:
            if self._source is SatelliteSource.FLYSAT:
                def get_sat(r):
                    return r[1], self.parse_position(r[2]), r[3], r[0], False

                return list(map(get_sat, filter(lambda x: all(x) and len(x) == 5, self._rows)))
            elif self._source is SatelliteSource.LYNGSAT:
                extra_pattern = re.compile("^https://www\.lyngsat\.com/[\w-]+\.html")
                base_url = "https://www.lyngsat.com/"
                sats = []
                current_pos = "0"
                for row in filter(lambda x: len(x) in (5, 7, 8), self._rows):
                    r_len = len(row)
                    if r_len == 7:
                        current_pos = self.parse_position(row[2])
                        name = row[1].rsplit("/")[-1].rstrip(".html").replace("-", " ")
                        sats.append((name, current_pos, row[5], base_url + row[1], False))  # [all in one] satellites
                        sats.append((row[4], current_pos, row[5], base_url + row[3], False))
                    if r_len == 8:  # for a very limited number of satellites
                        data = list(filter(None, row))
                        urls = set()
                        sat_type = ""
                        for d in data:
                            url = re.match(extra_pattern, d)
                            if url:
                                urls.add(url.group(0))
                            if d in ("C", "Ku", "CKu"):
                                sat_type = d
                        current_pos = self.parse_position(data[1])
                        for url in urls:
                            name = url.rsplit("/")[-1].rstrip(".html").replace("-", " ")
                            sats.append((name, current_pos, sat_type, base_url + url, False))
                    elif r_len == 5:
                        sats.append((row[2], current_pos, row[3], base_url + row[1], False))
                return sats

    def get_satellite(self, sat):
        pos = sat[1]
        return Satellite(name="{} {}".format(pos, sat[0]),
                         flags="0",
                         position=self.get_position(pos.replace(".", "")),
                         transponders=self.get_transponders(sat[3]))

    @staticmethod
    def parse_position(pos_str):
        return "".join(c for c in pos_str if c.isdigit() or c.isalpha() or c == ".")

    @staticmethod
    def get_position(pos):
        return "{}{}".format("-" if pos[-1] == "W" else "", pos[:-1])

    def get_transponders(self, sat_url):
        """ Getting transponders(sorted by frequency). """
        self._rows.clear()
        url = "https://www.flysat.com/" + sat_url if self._source is SatelliteSource.FLYSAT else sat_url
        request = requests.get(url=url, headers=self._HEADERS)
        reason = request.reason
        trs = []
        if reason == "OK":
            self.feed(request.text)
            if self._source is SatelliteSource.FLYSAT:
                self.get_transponders_for_fly_sat(trs)
            elif self._source is SatelliteSource.LYNGSAT:
                self.get_transponders_for_lyng_sat(trs)

        return sorted(trs, key=lambda x: int(x.frequency))

    def get_transponders_for_fly_sat(self, trs):
        """ Parsing transponders for FlySat """
        pls_pattern = re.compile("(PLS:)+ (Root|Gold|Combo)+ (\\d+)?")
        is_id_pattern = re.compile("(Stream) (\\d+)")
        pls_modes = {v: k for k, v in PLS_MODE.items()}
        n_trs = []

        if self._rows:
            zeros = "000"
            is_ids = []
            for r in self._rows:
                if len(r) == 1:
                    is_ids.extend(re.findall(is_id_pattern, r[0]))
                    continue
                if len(r) < 3:
                    continue
                data = r[2].split(" ")
                if len(data) != 2:
                    continue
                sr, fec = data
                data = r[1].split(" ")
                if len(data) < 3:
                    continue
                freq, pol, sys = data[0], data[1], data[2]
                sys = sys.split("/")
                if len(sys) != 2:
                    continue
                sys, mod = sys
                mod = "QPSK" if sys == "DVB-S" else mod

                pls = re.findall(pls_pattern, r[1])
                pls_code = None
                pls_mode = None

                if pls:
                    pls_code = pls[0][2]
                    pls_mode = pls_modes.get(pls[0][1], None)

                if is_ids:
                    tr = trs.pop()
                    for index, is_id in enumerate(is_ids):
                        tr = tr._replace(is_id=is_id[1])
                        if is_transponder_valid(tr):
                            n_trs.append(tr)
                else:
                    tr = Transponder(freq + zeros, sr + zeros, pol, fec, sys, mod, pls_mode, pls_code, None)
                    if is_transponder_valid(tr):
                        trs.append(tr)
                is_ids.clear()
            trs.extend(n_trs)

    def get_transponders_for_lyng_sat(self, trs):
        """ Parsing transponders for LyngSat """
        frq_pol_pattern = re.compile("(\\d{4,5})\\s+([RLHV]).*")
        sr_fec_pattern = re.compile("^(\\d{4,5})-(\\d/\\d)(.+PSK)?(.*)?$")
        sys_pattern = re.compile("(DVB-S[2]?) ?(PLS+ (Root|Gold|Combo)+ (\\d+))* ?(multistream stream (\\d+))?",
                                 re.IGNORECASE)
        zeros = "000"
        pls_modes = {v: k for k, v in PLS_MODE.items()}

        for r in filter(lambda x: len(x) > 8, self._rows):
            for frq in r[1], r[2], r[3]:
                freq = re.match(frq_pol_pattern, frq)
                if freq:
                    break
            if not freq:
                continue
            frq, pol = freq.group(1), freq.group(2)
            sr_fec = re.match(sr_fec_pattern, r[-3])
            if not sr_fec:
                continue
            sr, fec, mod = sr_fec.group(1), sr_fec.group(2), sr_fec.group(3)
            mod = mod.strip() if mod else "Auto"

            res = re.match(sys_pattern, r[-4])
            if not res:
                continue

            sys = res.group(1)
            pls_mode = res.group(3)
            pls_mode = pls_modes.get(pls_mode.capitalize(), None) if pls_mode else pls_mode
            pls_code = res.group(4)
            pls_id = res.group(6)

            tr = Transponder(frq + zeros, sr + zeros, pol, fec, sys, mod, pls_mode, pls_code, pls_id)
            if is_transponder_valid(tr):
                trs.append(tr)


if __name__ == "__main__":
    pass
