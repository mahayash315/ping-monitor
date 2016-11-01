# -*- coding: utf-8 -*-
import os
import smtplib
import yaml
from ConfigParser import ConfigParser
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from email import charset
from subprocess import Popen, PIPE
from logging import getLogger, Formatter, StreamHandler, FileHandler, DEBUG, INFO, WARNING, ERROR

UTF8 = 'utf-8'
COMMASPACE = ', '

PING_LOSS_PATTERN = '0 received'
PING_MESSAGE_PATTERN = 'icmp_seq=1 '

class PingMonitor(object):
	def __init__(self, config_file="ping-monitor.conf", targets_file="targets.yaml"):
		self._load_config(config_file, targets_file)
		self._verify_config()
		self._init_logger()

	def _load_config(self, config_file, targets_file):
		# config
		self.config = {
			'mailfrom': 'root',
			'mailto': 'root',
			'logfile': None,
			'loglevel': 'info'
		}
		parser = ConfigParser()
		parser.read(config_file)
		global_conf = dict(parser.items('global'))
		self.config = dict(self.config, **global_conf)
		
		# targets
		self.targets = {}
		with open(targets_file) as f:
			self.targets = dict(self.targets, **yaml.load(f))

	def _verify_config(self):
		# host
		for target, config in self.targets.items():
			if not ('host' in config):
				raise Exception("Property 'host' must be set for each target in targets config file")
		
		pass
	
	def _init_logger(self):
		self.logger = getLogger(__name__)

		formatter = Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s',
				      datefmt='%Y-%m-%d %H:%M:%S')

		log_level = self.config['loglevel'].lower()
		log_level = DEBUG   if log_level == 'debug'   else\
			    INFO    if log_level == 'info'    else\
			    WARNING if log_level == 'warning' else\
			    ERROR   if log_level == 'error'   else\
			    INFO
		self.logger.setLevel(log_level)
		
		stream_handler = StreamHandler()
		stream_handler.setLevel(log_level)
		self.logger.addHandler(stream_handler)
		
		if self.config['logfile'] != None:
			file_handler = FileHandler(self.config['logfile'], 'a+')
			file_handler.level = log_level
			file_handler.formatter = formatter
			self.logger.addHandler(file_handler)

	def monitor(self):
		for target, config in self.targets.items():
			try:
				self.logger.info('Begin monitor: ' + target)
				self.do_monitor(target, config)
				self.logger.info('End monitor: ' + target)
			except Exception as e:
				self.logger.error('Error: ' + str(e))

	def do_monitor(self, target, config):
		ping = Popen(
			['ping', '-c', '1', config['host']],
			stdout = PIPE,
			stderr = PIPE
		)
		out, error = ping.communicate()
		msg = ''
		success = True
		for line in out.splitlines():
			self.logger.debug('ping out: ' + line)
			
			if line.find(PING_MESSAGE_PATTERN) > -1:
				msg = line.split(PING_MESSAGE_PATTERN)[1]
			if line.find(PING_LOSS_PATTERN) > -1:
				success = False
		
		self.logger.debug('captured: ' + msg)
		
		if success:
			self.logger.info('Ping to ' + target + ' succeeded')
		else:
			self.logger.info('Ping to ' + target + ' failed')
			
			# send email
			date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			mailFrom = config['mailfrom'] if ('mailfrom' in config) else self.config['mailfrom']
			mailTo = config['mailto'] if ('mailto' in config) else self.config['mailto']
			subject = u'Ping to ' + target + ' failed'
			body  = u'' + date + u' ping to ' + config['host'] + u' failed.' + "\n"
			body += u'' + "\n"
			body += u'message sent by ping-monitor'
			self.sendmail(mailFrom, mailTo, subject, body)
			
			self.logger.info('Email sent to ' + COMMASPACE.join(mailTo))

	def sendmail(self, mailFrom, mailTo, subject, body):
		# format
		mailTo = mailTo if isinstance(mailTo, list) else [mailTo]
		
		# send
		con = smtplib.SMTP('localhost')
		con.set_debuglevel(True if self.config['loglevel'] == 'debug' else False)
		charset = UTF8
		message = MIMEText(body, 'plain', charset)
		message['Subject'] = Header(subject, charset)
		message['From'] = mailFrom
		message['To'] = COMMASPACE.join(mailTo)
		con.sendmail(mailFrom, mailTo, message.as_string())
		con.close()


if __name__ == '__main__':
	pingMonitor = PingMonitor()
	pingMonitor.monitor()
