__FILENAME__ = xorxes-ad7b52380d3ec704b28954c80119789a
# -*- coding: utf-8 -*-
import hashlib, struct, sys

def RROT(b, n, wsize):
	# eq to >>>, borrowed from bonsaiviking
    return ((b << (wsize-n)) & (2**wsize-1)) | (b >> n)

def SHA224(m):
	sha224 = hashlib.sha224() 
	sha224.update(m)
	return int(sha224.hexdigest(), 16)

def compress(m, c):
	assert len(m) == 1

	# calc sha224 on m
	x = SHA224(m)

	# rotate c by 28 bits xor with x
	return x ^ RROT(c, 56, 224)

# Xorxes Hash uses message blocks of 8-bits, with a 224-bit chaining variable.
#
#   (m_0)       (m_1)         ... (m_n)  = input message blocks
#     |           |                 |
#   SHA224      SHA224        ... SHA224    
#     |           |                 |
#  V-(+)-[>>>56]-(+)-[>>>56]- ... --+--- = chaining variable 
#
#  chaining variable + (message length mod 24) = hash output
#
def xorxes_hash(m):
	IV = ord('M') ^ ord('i') ^ ord('t') ^ ord('h') ^ ord('r') ^ ord('a')

	c = IV
	for mb in m:
		c = compress(mb, c)
	out = c + ( len(m) % 24 )
	return hex(out)[2:-1]

if  __name__ =='__main__':
	if not len(sys.argv) == 2:
		print "python xorxes.py [message]"
	else:
		print xorxes_hash(sys.argv[1])
########NEW FILE########
__FILENAME__ = rabinsbitch-0cd7a457fba750d8b1a3d120bc447327b40c123d
#
#for the answer take the hash of p,q concatenated together as decimal strings
#such as if p=7,q=11 p being by definition smaller you'd hash the string "711"
#please hash with sha512, thank you and g'luck

import math
import operator
import random,struct
import os,SocketServer
import base64 as b64

def encrypt(m,n):
    c=pow(m,2,n)
    return c
def extended_gcd(a, b):
    if b == 0:
       return (1, 0)
    else:
        (q, r) = (a/b, a%b)
        (s, t) = extended_gcd(b, r)
        return (t, s - q * t)
def invmod(a, p, maxiter=1000000):
    if a == 0:
        raise ValueError('0 has no inverse mod %d' % p)
    r = a
    d = 1
    for i in xrange(min(p, maxiter)):
        d = ((p // r + 1) * d) % p
        r = (d * a) % p
        if r == 1:
            break
    else:
        raise ValueError('%d has no inverse mod %d' % (a, p))
    return d

def reste_chinois(la,lm):
    """
    Return the solution of the Chinese theorem.
    """
    M = reduce(operator.mul, lm)
    lM = [M/mi for mi in lm]
    ly = map(invmod, lM, lm)
    laMy = map((lambda ai, Mi, yi : ai*Mi*yi), la, lM, ly)
    return sum(laMy) % M

def decrypt(c,p,q):
    mp=pow(c,(p+1)/4,p)
    mq=pow(c,(q+1)/4,q)
    r1 = pow(c, (p+1)/4, p)
    r2 = pow(c, (q+1)/4, q)

    return (reste_chinois([r1, r2], [p, q]), \
                reste_chinois([-r1, r2], [p, q]), \
                reste_chinois([r1, -r2], [p, q]), \
                reste_chinois([-r1, -r2], [p, q]))    
p=7
q=11
n=p*q
TEST=True
if TEST:
    m=[]
    for x in xrange(200):
        m.append(random.getrandbits(1200))
    print m[0]
    print len(set(m))
    assert(len(set(m))>2)
    i=0
    print decrypt(3,p,q)
    for x in m:
        enc=encrypt(x,n)
        if i%20==0:
            print "ENCRYPTED IS %r" %enc
        i+=1
        assert(x in decrypt(enc,p,q) )

class  SignHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        req=self.request
		req.sendall("You must first solve a puzzle, a sha1 sum ending in 26 bit's set to 1, it must be of length %s bytes, starting with %s"%(len(proof)+5,proof))
		test=req.recv(21)
		ha=hashlib.sha1()
		ha.update(test)
		if (test[0:16]!=proof or ord(ha.digest()[-1])!=0xff or 
            ord(ha.digest()[-2])!=0xff or
			ord(ha.digest()[-3])!=0xff or
			ord(ha.digest()[-4])&3!=3 
			):
			req.sendall("NOPE")
			req.close()
			return

        leng=struct.unpack("H",req.recv(2))[0]
        s=""
        while len(s)<leng:
            s+=req.recv(leng-len(s))
        if len(s)> leng:
            req.sendall("Okaly Doakaly")
            req.close()
            return
        i=0
        s=s[::-1]
        for el in xrange(len(s)):
            i+=(ord(s[el])<<(8*el))
        rets=decrypt(i,p,q)
        for el in rets[:-1]:
            req.sendall(str(el)+",")
        req.sendall(str(rets[-1]))


        req.close()


class ThreadedServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
   pass
if __name__ == "__main__" and not TEST:
   HOST, PORT = "", 9955
   server = ThreadedServer((HOST, PORT), SignHandler)
   server.allow_reuse_address = True
   server.serve_forever()

########NEW FILE########
__FILENAME__ = subme-e9678f31ce09407931e4dfacef649cd935b66932
#Decrypt 'f\x1c\xfc\xff5\xc3\xeej\xac\xd1\xba\x92?\xe9\xa3Y'
#with the proper key for the answer, g'luck
s = [ 0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76, 0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0, 0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15, 0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75, 0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84, 0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF, 0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8, 0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2, 0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73, 0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB, 0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79, 0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08, 0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A, 0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E, 0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF, 0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16] 
sinv = [ 0x52, 0x09, 0x6A, 0xD5, 0x30, 0x36, 0xA5, 0x38, 0xBF, 0x40, 0xA3, 0x9E, 0x81, 0xF3, 0xD7, 0xFB, 0x7C, 0xE3, 0x39, 0x82, 0x9B, 0x2F, 0xFF, 0x87, 0x34, 0x8E, 0x43, 0x44, 0xC4, 0xDE, 0xE9, 0xCB, 0x54, 0x7B, 0x94, 0x32, 0xA6, 0xC2, 0x23, 0x3D, 0xEE, 0x4C, 0x95, 0x0B, 0x42, 0xFA, 0xC3, 0x4E, 0x08, 0x2E, 0xA1, 0x66, 0x28, 0xD9, 0x24, 0xB2, 0x76, 0x5B, 0xA2, 0x49, 0x6D, 0x8B, 0xD1, 0x25, 0x72, 0xF8, 0xF6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xD4, 0xA4, 0x5C, 0xCC, 0x5D, 0x65, 0xB6, 0x92, 0x6C, 0x70, 0x48, 0x50, 0xFD, 0xED, 0xB9, 0xDA, 0x5E, 0x15, 0x46, 0x57, 0xA7, 0x8D, 0x9D, 0x84, 0x90, 0xD8, 0xAB, 0x00, 0x8C, 0xBC, 0xD3, 0x0A, 0xF7, 0xE4, 0x58, 0x05, 0xB8, 0xB3, 0x45, 0x06, 0xD0, 0x2C, 0x1E, 0x8F, 0xCA, 0x3F, 0x0F, 0x02, 0xC1, 0xAF, 0xBD, 0x03, 0x01, 0x13, 0x8A, 0x6B, 0x3A, 0x91, 0x11, 0x41, 0x4F, 0x67, 0xDC, 0xEA, 0x97, 0xF2, 0xCF, 0xCE, 0xF0, 0xB4, 0xE6, 0x73, 0x96, 0xAC, 0x74, 0x22, 0xE7, 0xAD, 0x35, 0x85, 0xE2, 0xF9, 0x37, 0xE8, 0x1C, 0x75, 0xDF, 0x6E, 0x47, 0xF1, 0x1A, 0x71, 0x1D, 0x29, 0xC5, 0x89, 0x6F, 0xB7, 0x62, 0x0E, 0xAA, 0x18, 0xBE, 0x1B, 0xFC, 0x56, 0x3E, 0x4B, 0xC6, 0xD2, 0x79, 0x20, 0x9A, 0xDB, 0xC0, 0xFE, 0x78, 0xCD, 0x5A, 0xF4, 0x1F, 0xDD, 0xA8, 0x33, 0x88, 0x07, 0xC7, 0x31, 0xB1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xEC, 0x5F, 0x60, 0x51, 0x7F, 0xA9, 0x19, 0xB5, 0x4A, 0x0D, 0x2D, 0xE5, 0x7A, 0x9F, 0x93, 0xC9, 0x9C, 0xEF, 0xA0, 0xE0, 0x3B, 0x4D, 0xAE, 0x2A, 0xF5, 0xB0, 0xC8, 0xEB, 0xBB, 0x3C, 0x83, 0x53, 0x99, 0x61, 0x17, 0x2B, 0x04, 0x7E, 0xBA, 0x77, 0xD6, 0x26, 0xE1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0C, 0x7D ]

import array
import hashlib,struct
from itertools import *
import os,SocketServer
import base64 as b64
key=""
h=hashlib.sha512()
h.update(key)
ha=h.digest()
k1,k2,k3=array.array("B",ha[0:8]),array.array("B",ha[8:16]),array.array("B",ha[16:24])[::-1]

def subStr(toSub):
   sub= lambda x: s[x]
   toSub=map(sub,toSub)
   return toSub

lper,luper=([51, 43, 42, 47, 19, 49, 10, 23, 18, 11, 1, 60, 24, 31, 40, 54, 12, 56, 38, 59, 52, 6, 50, 13, 53, 34, 27, 17, 2, 3, 29, 26, 21, 30, 62, 20, 45, 16, 39, 28, 48, 35, 15, 22, 63, 58, 32, 57, 25, 33, 14, 36, 44, 37, 0, 8, 41, 5, 7, 9, 55, 46, 4, 61], [54, 10, 28, 29, 62, 57, 21, 58, 55, 59, 6, 9, 16, 23, 50, 42, 37, 27, 8, 4, 35, 32, 43, 7, 12, 48, 31, 26, 39, 30, 33, 13, 46, 49, 25, 41, 51, 53, 18, 38, 14, 56, 2, 1, 52, 36, 61, 3, 40, 5, 22, 0, 20, 24, 15, 60, 17, 47, 45, 19, 11, 63, 34, 44])
for el in xrange(len(luper)):
   assert(luper[lper[el]]==el)

def permute(strry):
   p1=struct.unpack("Q",strry)[0]
   rP1=0L
   for el,el2 in zip(xrange(len(luper)),lper):
      isSet1=(p1&(1L<<el))>>el
      rP1|=(isSet1<<el2)
   return struct.pack("Q",rP1)
def unPermute(strry):
   try:
      p1=struct.unpack("Q",strry)[0]
   except:
      print "#"*200
      print "%r %d" %(strry,len(strry))
      print "#"*200
      p1=1
   rP1=0L
   for el,el2 in zip(xrange(len(luper)),luper):
      isSet1=(p1&(1<<el))>>el
      rP1|=(isSet1<<el2)
   return struct.pack("Q",rP1)




def unSubStr(toSub):
   sub= lambda x: sinv[x]
   toSub=map(sub,toSub)
   return toSub


from collections import deque
def encrypt(strry):
   toEnc= array.array("B",strry)
   global k1,k2,k3
   for el in xrange(len(k1)):
      toEnc[el]=toEnc[el]^k1[el]

   toEnc=subStr(toEnc)
   toEnc=map(ord,permute("".join(map(chr,toEnc))))
   
   for el in xrange(len(k2)):
      toEnc[el]=toEnc[el]^k2[el]
   toEnc=subStr(toEnc)
   toEnc=map(ord,permute("".join(map(chr,toEnc))))

   ints=0
   kadd=0
   toEnc.reverse()
   #defeat linearity to beat off the sat solvers
   for el in xrange(len(toEnc)): 
      ints+=((toEnc[el])<<(8*el))
      kadd+=((k3[el])<<(8*el))
   ints+=kadd
   ints=ints%18446744073709551615
   ret=struct.pack("Q",ints)
   return ret


def decrypt(strry):
   toDec=struct.unpack("Q",strry)[0]
   global k1,k2,k3
   kadd=0
   
   for el in xrange(8): 
      kadd+=((k3[el])<<(8*el))
   toDec-=kadd
   ints=toDec%18446744073709551615
   toDec=[]
   while ints>0:
      toDec.append(int(ints&0xff))
      ints=ints>>8
   while len(toDec)<8:
      toDec.append(0)
   toDec.reverse()

   toDec=map(ord,unPermute("".join(map(chr,toDec))))
   toDec=unSubStr(toDec)

   for el in xrange(len(k1)):
      toDec[el]=toDec[el]^k2[el]
   
   toDec=map(ord,unPermute("".join(map(chr,toDec))))
   toDec=unSubStr(toDec)

   for el in xrange(len(k1)):
      toDec[el]=toDec[el]^k1[el]
   ret=toDec
   return "".join(map(chr,ret))

class  SignHandler(SocketServer.BaseRequestHandler):
   def handle(self):
      req=self.request
      proof=b64.b64encode(os.urandom(12))
      req.sendall("You must first solve a puzzle, a sha1 sum ending in 16 bit's set to 1, it must be of length %s bytes, starting with %s"%(len(proof)+5,proof))
      test=req.recv(21)
      ha=hashlib.sha1()
      ha.update(test)
      if test[0:16]!=proof or ord(ha.digest()[-1])!=0xff or ord(ha.digest()[-2])!=0xff:
         req.sendall("NOPE")
         req.close()
         return

      leng=struct.unpack("H",req.recv(2))[0]
      if leng%8!=0:
         req.sendall("Must be a full block size aka mod 8")
         req.close()
         return
      s=""
      while len(s)<leng:
         s+=req.recv(leng-len(s))
      if len(s)> leng:
         req.sendall("Nice try asshole")
         req.close()
         return
      rets=""
      for x in xrange(0,leng,8):
         rets+=encrypt(s[x:x+8])
      req.sendall("HERE IS YOUR STRING %r"%rets)
      req.close()





class ThreadedServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
   pass

def sanityCheck():
   for x in xrange(500000):
      toCheck=os.urandom(8)
      blah=encrypt(toCheck)
      assert(toCheck==decrypt(blah))
#sanityCheck()

if __name__ == "__main__":
   HOST, PORT = "", 9999
   server = ThreadedServer((HOST, PORT), SignHandler)
   server.allow_reuse_address = True
   server.serve_forever()

########NEW FILE########
