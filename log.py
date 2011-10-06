# -*- coding: utf-8 -*-
# log.py --- Time-stamp: <2010-07-08 12:47:58 Thursday by julian>
# Copyright 2010 Julian Qian
# Author: julian@PDDES.cdc.veritas.com
# Version: $Id: log.py,v 0.0 2010/07/08 04:32:27 julian Exp $
# Keywords: 

"""
<log.config>

[loggers]
keys=root

[handlers]
keys=hand01

[formatters]
keys=fm01

[logger_root]
level=DEBUG
handlers=hand01

[handler_hand01]
class=FileHandler
level=DEBUG
formatter=fm01
args=('crawl.log', 'a')

[formatter_fm01]
format=%(asctime)s %(levelname)-8s %(message)s
"""
import logging
import logging.config
import inspect
import os

class CrawlLog(object):
    """
    """
    
    def __init__(self, cfgfile):
        logging.config.fileConfig(cfgfile)
	self.mylogger = logging.getLogger()

    def __init__(self):
	self.mylogger = logging.getLogger()
	hdlr = logging.FileHandler('crawl.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
	hdlr.setFormatter(formatter)
	self.mylogger.addHandler(hdlr)
	self.mylogger.setLevel(logging.NOTSET)

    def debug(self, msg, *args, **kwargs):
	self.mylogger.debug(self._add_module_line(msg), *args, **kwargs)

    def info(self, msg, *args, **kwargs):
	self.mylogger.info(self._add_module_line(msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
	self.mylogger.warning(self._add_module_line(msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
	self.mylogger.error(self._add_module_line(msg), *args, **kwargs)
	
    def critical(self, msg, *args, **kwargs):
	self.mylogger.critical(self._add_module_line(msg), *args, **kwargs)
	
    def _add_module_line(self, msg):
	_, modulepath, line, _, _, _ = inspect.stack()[-1]
	head, tail = os.path.split(modulepath)
	return tail + ' (' + str(line) + '): ' + msg

logger = CrawlLog()


def main():
    a = 99
    logger.debug('Test Debug a = %s', a)
    logger.error('Test Error!')
    logger.info('info here')
    
if __name__ == "__main__":
    main()    
