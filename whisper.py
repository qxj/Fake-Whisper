#!/usr/bin/env python
# -*- coding: utf-8 -*-
# whisper.py --- Time-stamp: <Julian Qian 2011-10-29 22:22:46>
# Copyright 2011 Julian Qian
# Author: junist@gmail.com
# Version: $Id: whisper.py,v 0.0 2011/08/15 06:10:33 jqian Exp $


import poplib, email, string, subprocess, os, time, sqlite3
import urllib, urllib2, cookielib
import ConfigParser, getopt, sys, random
from log import logger

WHISPER_PATH="/var/tmp/whisper/"
KINDLEGEN_PATH="/usr/local/bin/kindlegen"

SOURCES = {"mail":1, "instapaper":2}

def whisper_path(filename):
    return os.path.join(WHISPER_PATH, filename)

def unique_id(filename):
    return "%s%d" % (time.strftime("%y%m%d"), random.getrandbits(16))

def kindlegen(filename):
    basename, ext = os.path.splitext(filename)
    targetfile = basename + ".mobi"
    targetname = os.path.basename(targetfile)
    cmd = '%s %s -o "%s" >> /var/tmp/kindlegen-log.txt' % (KINDLEGEN_PATH, filename, targetname)
    logger.debug(cmd)
    subprocess.call(cmd, shell=True)
    if os.path.exists(targetfile):
        return os.path.getsize(targetfile)
    else:
        return None

class WhisperDb(object):
    """
    Store files to be downloaded.
    """

    def __init__(self, dbfile = '/var/tmp/whisper.db'):
        is_init = False
        if os.path.isfile(dbfile) and os.path.exists(dbfile):
            is_init = True
        else:
            open(dbfile, "w").close()

        self.conn = sqlite3.connect(dbfile)
        if not is_init:         # init database
            c = self.conn.cursor()
            c.execute("create table files (fileid text, filename text, filetype text, filesize integer, source integer, timestamp integer, downloaded integer)")       # file is primary key
            self.conn.commit()
            c.close()

    def close(self):
        self.conn.close()

    def put_file(self, fileid, filename, filetype, filesize, source):
        c = self.conn.cursor()
        c.execute("insert into files (fileid, filename, filetype, filesize, timestamp, source, downloaded) values (:fileid, :filename, :filetype, :filesize, :timestamp, :source, 0)", {"fileid": fileid, "filename": filename, "filetype": filetype, "filesize": int(filesize), "timestamp": int(time.time()), "source": source})
        self.conn.commit()
        c.close()

    def last_size(self, source):
        c = self.conn.cursor()
        c.execute("select filesize from files where source= :source order by timestamp desc limit 1",{"source": source})
        row = c.fetchone()
        c.close()
        if row:
            return row[0]
        return None

class MailParser(object):
    """
    Parse message into seperated files.
    """

    def __init__(self):
        self._db = WhisperDb()

    def parse(self, message):
        # begin to parse message
        mail = email.message_from_string(string.join(message, '\n'))
        header = email.Header.decode_header(mail.get('subject'))
        title, charset = header[0]
        logger.info("parse mail: %s" % (title))
        count = 0
        for part in mail.walk():
            if not part.is_multipart():
                partname = part.get_filename()
                filename = None
                if not partname:
                    if part.get_content_type() == 'text/html':
                        filename = title
                        filetype = ".html"
                else:
                    filename, filetype = os.path.splitext(partname)
                if filename:
                    content = part.get_payload(decode=True)
                    if content:
                        # add <body> tag into content, otherwise
                        # kindlegen can't recognize such formats.
                        if -1 == content.find("<body>"):
                            content = content.replace("<html>", "<body>").replace("</html>", "</body>")
                        fileid = unique_id(filename)
                        filesize = len(content)
                        targetfile = fileid + filetype
                        fp = open(whisper_path(targetfile), 'wb')
                        fp.write(content)
                        fp.close()
                        # if html/epub but not pdf, transcode them to mobi format
                        if filetype.lower() in (".html", ".epub"):
                            filesize = kindlegen(whisper_path(targetfile))
                            filetype = ".mobi"
                        if filesize and filetype in (".pdf", ".mobi"):
                            logger.info("restore file %s as %s.%s in sqlite." % (filename, fileid, filetype ))
                            self._db.put_file(fileid, filename, filetype, filesize, SOURCES["mail"])
                            count += 1
        return count

class FetchMail(object):
    """
    """

    def __init__(self, user, passwd):
        """

        Arguments:
        - `user`:
        - `passwd`:
        """
        self._user = user
        self._passwd = passwd
        self._parser = MailParser()

    def run(self):
        server = poplib.POP3_SSL('pop.gmail.com', '995')
        server.user(self._user)
        server.pass_(self._passwd)
        msgCnt, msgSize = server.stat()
        logger.info("retrieving message count: %d, size: %d" % (msgCnt, msgSize))
        for i in range(msgCnt):
            try:
                hdr, message, octet = server.retr(i)
                logger.info("retrieved message %d: %s" % (i, hdr))
                count = self._parser.parse(message)
                logger.info("parse message to %d parts." % count)
            except poplib.error_proto, e:
                logger.error("failed to retr message %d" % (i))
        logger.info("fetch mail end.")


    # attachment
    # 1. parts = mail.get_payloads() or
    #    for part in msg.walk():
    #        part.get_content_type()
    # 2. mimetype = parts[i].get_content_type()
    # 3. filename = parts[i].get_filename()
    # 4. content = parts[i].get_payload(decode=True)

class FetchInstapaper(object):
    """
    """

    def __init__(self, user, passwd):
        """

        Arguments:
        - `user`:
        - `passwd`:
        """
        self._user = user
        self._passwd = passwd
        self._db = WhisperDb()


    def login(self):
        cookie_support = urllib2.HTTPCookieProcessor(cookielib.CookieJar())
        opener = urllib2.build_opener(cookie_support, urllib2.HTTPHandler)
        urllib2.install_opener(opener)
        postdata = urllib.urlencode({
                'username': self._user,
                'password': self._passwd
                })
        postheaders = {
            "User-Agent":"Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11",
            "Content-Type":"application/x-www-form-urlencoded",
            "Referer":"http://www.instapaper.com/user/login",
            "Connection":"keep-alive",
            "Keep-Alive":115
            }
        req = urllib2.Request(
            url = "http://www.instapaper.com/user/login",
            data = postdata,
            headers = postheaders
            )
        try:
            res = urllib2.urlopen(req)
        except URLError, e:
            logger.error("instapaper url failed:" + e.reason)
        else:
            logger.info("Succeed to login instapaper")
            # TODO: check html content
            return True
        logger.error("Failed to login instapaper")
        return False

    def download(self):
        url = "http://www.instapaper.com/mobi"
        try:
            res = urllib2.urlopen(url)
        except URLError, e:
            logger.error("crawl failed: " + url + ": " + e.reason)
        else:
            logger.info("succeed to crawl url: " + url)
            content = res.read()
            # check duplicated
            #
            # NOTE: we'd better only check file size but not their checksum.
            #
            lastsize = self._db.last_size(SOURCES["instapaper"])
            if lastsize != len(content):
                filename = "Instapaper-%s.mobi" % (time.strftime("%Y-%m-%d"))
                fp = open(whisper_path(filename), "wb")
                fp.write(content)
                fp.close()
                fileid = unique_id(filename)
                logger.info("instapaper save %s to %s.mobi." % (filename, fileid))
                self._db.put_file(fileid, filename, ".mobi", len(content), SOURCES["instapaper"])

    def run(self):
        if self.login():
            self.download()
        logger.info("fetch instapaper end.")


def main():
    """
    Fake whispernet
    """
    config = ConfigParser.ConfigParser()
    config.read("whisper.conf")

    if not os.path.exists(KINDLEGEN_PATH):
        print "kindlegen can't be found."
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "gi", ["gmail", "instapaper"])
    except getopt.GetoptError, e:
        print e
        sys.exit(2)
    if opts:
        for o, a in opts:
            if o in ("-g", "--gmail"):
                fmail = FetchMail(config.get('GMAIL', 'USERNAME'),
                                  config.get('GMAIL', 'PASSWORD'))
                fmail.run()
            elif o in ("-i", "--instapaper"):
                finst = FetchInstapaper(config.get('INSTAPAPER', 'USERNAME'),
                                        config.get('INSTAPAPER', 'PASSWORD'))
                finst.run()
            else:
                print "wrong arguments."

if __name__ == "__main__":
    main()
