#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Implements a variant of session tickets as proposed for TLS in RFC 5077:
https://tools.ietf.org/html/rfc5077
"""

import os
import random
import time
import const

from Crypto.Cipher import AES
from Crypto.Hash import HMAC
from Crypto.Hash import SHA256

import mycrypto

# Length of the ticket's name which is used to quickly identify issued tickets.
NAME_LENGTH = 16

# Length of the IV which is used for AES-CBC.
IV_LENGTH = 16

# Must be a multiple of 16 bytes due to AES' block size.
IDENTIFIER = "ScrambleSuitTicket"


def decryptTicket( ticket ):
	"""Verifies the validity, decrypts and finally returns the given potential
	ticket as a ProtocolState object. If the ticket is invalid, `None' is
	returned."""

	assert len(ticket) == const.SESSION_TICKET_LENGTH

	# Did we previously issue this key name?
	if not (ticket[:16] == keyName):
		log.debug("Ticket name not found. We are not dealing with a ticket.")
		return None

	# Verify if HMAC is correct.
	hmac = HMAC.new(globalHMACKey, ticket[:-32], digestmod=SHA256).digest()
	if not hmac == ticket[-32:]:
		log.debug("Invalid HMAC. Probably no ticket.")
		return None

	# Decrypt ticket to obtain state.
	aes = AES.new(globalAESKey, mode=AES.MODE_CBC, IV=ticket[16:32])
	plainTicket = aes.decrypt(ticket[32:-32])

	issueDate = plainTicket[:10]
	identifier = plainTicket[10:28]
	if not (identifier == IDENTIFIER):
		log.error("Invalid identifier. This could be a bug.")
		return None
	masterKey = plainTicket[28:44]
	return ProtocolState(masterKey, issueDate)


class ProtocolState( object ):
	"""Describes the protocol state of a ScrambleSuit server which is part of a
	session ticket. The state can be used to bootstrap a ScrambleSuit session
	without the client unlocking the puzzle."""

	def __init__( self, masterKey, issueDate=int(time.time()) ):
		self.identifier = IDENTIFIER
		#self.protocolVersion = None
		self.masterKey = masterKey
		#self.clientIdentity = None
		self.issueDate = None
		# Pad to multiple of 16 bytes due to AES' block size.
		self.pad = "\0\0\0\0"


	def isValid( self ):
		"""Returns `True' if the protocol state is valid, i.e., if the life time
		has not expired yet. Otherwise, `False' is returned."""

		assert issueDate
		now = int(time.time())

		if (now - self.issueDate) > const.SESSION_TICKET_LIFETIME:
			return False

		return True


	def __repr__( self ):

		return self.issueDate + self.identifier + self.masterKey + self.pad


class SessionTicket( object ):
	"""Encapsulates a session ticket which can be used by the client to gain
	access to a ScrambleSuit server without solving the served puzzle."""

	def __init__( self, masterKey, symmTicketKey, hmacTicketKey ):
		"""Initialize a new session ticket which contains `masterKey'. The
		parameter `symmTicketKey' is used to encrypt the ticket and
		`hmacTicketKey' is used to authenticate the ticket when issued."""

		assert len(masterKey) == len(symmTicketKey) == len(hmacTicketKey) == 16

		# The random name is used to recognize previously issued tickets.
		self.keyName = mycrypto.weak_random(NAME_LENGTH)

		# Initialization vector for AES-CBC.
		self.IV = mycrypto.strong_random(IV_LENGTH)

		# The server's actual (encrypted) protocol state.
		self.state = ProtocolState(masterKey)

		# AES and HMAC key to protect the ticket.
		self.symmTicketKey = symmTicketKey
		self.hmacTicketKey = hmacTicketKey


	def issue( self ):
		"""Encrypt and authenticate the ticket and return the result which is
		ready to be sent over the wire. In particular, the ticket name (for
		bookkeeping) as well as the actual encrypted ticket is returned."""

		self.state.issueDate = "%d" % time.time()

		# Encrypt the protocol state.
		aes = AES.new(self.symmTicketKey, mode=AES.MODE_CBC, IV=self.IV)
		state = repr(self.state)
		assert (len(state) % AES.block_size) == 0
		cryptedState = aes.encrypt(state)

		# Authenticate ticket name, IV and the encrypted state.
		hmac = HMAC.new(self.hmacTicketKey, self.keyName + self.IV + \
				cryptedState, digestmod=SHA256).digest()

		ticket = self.keyName + self.IV + cryptedState + hmac

		return (self.keyName, ticket)


# Alias class name in order to provide a more intuitive API.
new = SessionTicket
