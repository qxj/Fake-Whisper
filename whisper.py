#!/usr/bin/env python
# -*- coding: utf-8 -*-
# whisper.py --- Time-stamp: <Julian Qian 2012-11-25 12:13:40>
# Copyright 2011, 2012 Julian Qian
# Author: junist@gmail.com
# Version: $Id: whisper.py,v 0.0 2011/08/15 06:10:33 jqian Exp $

import imaplib, email, string, subprocess, os, time, sqlite3, logging
import urllib, urllib2, cookielib, socket
import ConfigParser, getopt, sys, random

WHISPER_PATH="/var/tmp/whisper/"
KINDLEGEN_PATH="/usr/local/bin/kindlegen"

SOURCES = {"mail":1, "instapaper":2}

def getLogger():
    logger = logging.getLogger('whisper')
    logger.setLevel(logging.DEBUG)
    ## append to file
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    # fh = logging.FileHandler('whisper.log')
    # fh.setLevel(logging.DEBUG)
    # fh.setFormatter(formatter)
    # logger.addHandler(fh)
    ## append to sys.stderr
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

logger = getLogger()

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
            conn = sqlite3.connect(dbfile)
            c = conn.cursor()
            try:
                c.execute("select * from files limit 1")
                is_init = True
            except:
                pass
            c.close()
            conn.close()
        else:
            open(dbfile, "w").close()

        self.conn = sqlite3.connect(dbfile)
        if not is_init:         # init database
            c = self.conn.cursor()
            c.execute("create table files (fileid text, filename text, filetype text, filesize integer, source integer, timestamp integer, downloaded integer)")       # fileid is primary key
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
        mail = email.message_from_string(message)
        header = email.Header.decode_header(mail.get('subject'))
        title, charset = header[0]
        try:
            title = title.decode(charset, "ignore")
        except:
            logger.error("failed to decode %s with %s" % (title, charset))
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
                    # FIXME: gbk encoding partname
                    filetype = filetype.replace("?=", "")
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
        try:
            server = imaplib.IMAP4_SSL('imap.gmail.com')
            server.login(self._user, self._passwd)
            result, dummy = server.select('INBOX')
            if result != 'OK':
                logger.error('failed to select INBOX of gmail')
            else:
                result, data = server.uid('search', None, 'UnSeen')
                # date = (datetime.date.today() - datetime.timedelta(1)).strftime("%d-%b-%Y")
                # result, data = mail.uid('search', None, '(SENTSINCE {date})'.format(date=date))

                if result != 'OK':
                    logger.error('failed to get messages')
                elif data:
                    uids = data[0].split()
                    logger.info("retrieving message...")
                    for uid in uids:
                        result, msg = server.uid('fetch', uid, '(RFC822)')
                        message = msg[0][1]
                        logger.info("retrieved message %s" % (uid))
                        count = self._parser.parse(message)
                        logger.info("parse message to %d parts." % count)
                    logger.info("fetch mail end.")
                    server.store(data[0].replace(' ',','),'+FLAGS','Seen')
                    logger.info("mark mail as seen.")
                server.close()
                server.logout()
        except socket.error, e:
            logger.error("error open imap connection.")
        except imaplib.IMAP4.error, e:
            logger.error("error during imap connection")

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
                filename = "Instapaper-%s" % (time.strftime("%Y-%m-%d"))
                filetype = ".mobi"
                fileid = unique_id(filename)
                targetfile = fileid + filetype
                fp = open(whisper_path(targetfile), "wb")
                fp.write(content)
                fp.close()
                logger.info("instapaper save %s to %s." % (filename, targetfile))
                self._db.put_file(fileid, filename, filetype, len(content), SOURCES["instapaper"])

    def run(self):
        if self.login():
            self.download()
        logger.info("fetch instapaper end.")


def main():
    """
    Fake whispernet
    """
    config = ConfigParser.ConfigParser()

    if not os.path.exists(KINDLEGEN_PATH):
        print "kindlegen can't be found."
        sys.exit(1)

    if not os.path.exists(WHISPER_PATH):
        os.makedirs(WHISPER_PATH)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:gi", ["conf", "gmail", "instapaper"])
    except getopt.GetoptError, e:
        print e
        sys.exit(2)
    if opts:
        for o, a in opts:
            if o in ("-c", "--conf"):
                config.read(a)
                print "read setting file %s" % (a)
                break
        else:
            conf = os.path.dirname(sys.argv[0]) + "/whisper.conf"
            config.read(conf)
            print "no whisper.conf is specified, apply the default: %s." % conf
        for o, a in opts:
            if o in ("-g", "--gmail"):
                try:
                    u = config.get('GMAIL', 'USERNAME')
                    p = config.get('GMAIL', 'PASSWORD')
                    print "fetching gmail account %s" % u
                    fmail = FetchMail(u, p)
                    fmail.run()
                except ConfigParser.Error, e:
                    print "failed to get gmail setting!"
                    sys.exit(2)
            elif o in ("-i", "--instapaper"):
                try:
                    u = config.get('INSTAPAPER', 'USERNAME')
                    p = config.get('INSTAPAPER', 'PASSWORD')
                    print "fetching instapaper account %s" % u
                    finst = FetchInstapaper(u, p)
                    finst.run()
                except ConfigParser.Error, e:
                    print "failed to get instapaper setting!"
                    sys.exit(2)

if __name__ == "__main__":
    main()
