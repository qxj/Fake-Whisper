#!/usr/bin/env python
# -*- coding: utf-8 -*-
# whisper.py --- Time-stamp: <Julian Qian 2011-10-06 17:13:38>
# Copyright 2011 Julian Qian
# Author: junist@gmail.com
# Version: $Id: whisper.py,v 0.0 2011/08/15 06:10:33 jqian Exp $


import poplib, email, string, subprocess, os, time, sqlite3
import urllib, urllib2, cookielib
import ConfigParser
from log import logger

WHISPER_PATH="/var/tmp/whisper/"

SOURCES = {"mail":1, "instapaper":2}

def whisper_path(filename):
    return os.path.join(WHISPER_PATH, filename)

def unique_id(filename):
    return time.strftime("%y%m%d%H%M%S")

def kindlegen(filename):
    basename, ext = os.path.splitext(filename)
    targetfile = basename + ".mobi"
    cmd = 'kindlegen %s -o "%s" >> /var/tmp/kindlegen-log.txt' % (filename, targetfile)
    logger.debug(cmd)
    subprocess.call(cmd, shell=True)
    return os.path.getsize(targetfile)

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
        c.execute("insert into files (fileid, filename, filetype, filesize, timestamp, source, downloaded) values (:fileid, :filename, :filetype, :filesize, :timestamp, :source, 0)", {"fileid": fileid, "filename": filename, "filetype": filetype, "filesize": filesize, "timestamp": int(time.time()), "source": source})
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

    def __init__(self, message, db):
        # begin to parse message
        mail = email.message_from_string(string.join(message, '\n'))
        title = email.Header.decode_header(mail.get('subject'))
        logger.info("parse mail: %s" % (title))
        for part in mail.walk():
            if not part.is_multipart():
                partname = part.get_filename()
                if not partname:
                    if part.get_content_type() == 'text/html':
                        filename = title
                        filetype = "html"
                else:
                    filename, filetype = os.path.splitext(partname)
                if filename:
                    content = part.get_payload(decode=True)
                    if content:
                        fileid = unique_id(filename)
                        filesize = len(content)
                        targetfile = fileid +"."+ filetype
                        fp = open(whisper_path(targetfile), 'wb')
                        fp.write(content)
                        fp.close()
                        # if not pdf, transcode to mobi format
                        if filetype.lower() != "pdf":
                            filesize = kindlegen(whisper_path(targetfile))
                            filetype = "mobi"
                        db.put_file(filename, filetype, filesize, SOURCES["mail"])

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
        self._db = WhisperDb()

    def run(self):
        server = poplib.POP3_SSL('pop.gmail.com', '995')
        server.user(self._user)
        server.pass_(self._passwd)
        msgCnt, msgSize = server.stat()
        for i in range(msgCnt):
            hdr, message, octet = server.retr(i)
            MailParser(message, self._db)


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
        except HTTPError, e:
            logger.error("instapaper http failed:" + e.reason)
        except URLError, e:
            logger.error("instapaper url failed:" + e.reason)
        else:
            logger.info("Succeed to login instapaper")
            # TODO: check html content
            return True
        return False

    def download(self):
        url = "http://www.instapaper.com/mobi"
        try:
            res = urllib2.urlopen(url)
        except HTTPError, e:
            logger.error("crawl failed: " + url + ": " + e.reason)
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
                print filename
                fp = open(whisper_path(filename), "wb")
                fp.write(content)
                fp.close()
                self._db.put_file(filename, "mobi", len(content), SOURCES["instapaper"])

    def run(self):
        if self.login():
            self.download()

def main():
    """
    Fake whispernet
    """
    config = ConfigParser.ConfigParser()
    config.read("whisper.conf")

    fmail = FetchMail(config.get('GMAIL', 'USERNAME'),
                      config.get('GMAIL', 'PASSWORD'))
    fmail.run()

    finst = FetchInstapaper(config.get('INSTAPAPER', 'USERNAME'),
                            config.get('INSTAPAPER', 'PASSWORD'))
    finst.run()

if __name__ == "__main__":
    main()
