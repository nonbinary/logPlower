#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""a script to plow through numerous logs, exctracting lines that are within a specified time window"""

import sys, argparse, time
import os, errno
import string

# standard log files to always include in every search
stdLogFiles = ('/var/log/syslog', '/var/log/kern.log', '/var/log/auth.log',)

# argparser accepts quite specific functions as formatters. So here is one
def parseTime(argString):
    # we have two acceptable formats. Try one
    try:
        return(time.strptime(argString, "%Y-%m-%d"))
    except:
        # if that didn't work, try the other
        try:
            return(time.strptime(argString, "%H:%M:%S"))
        # and if that still didn't work, rase exception
        except:
            raise

# argparser can't handle wildcards in their "type=file"-handling, so we'll have to just use path-strings
def parsePath(argString):
    if os.path.exists(argString):
        return(argString)
    else:
        raise errno.ENOENT

# join date from a date, timeDate, and time, timeTime, to one time-tuple.
# time info from timeDate will be discarded, as well as date info from timeTime
def joinTime(timeDate,timeTime):
    return time.mktime(
            (timeDate.tm_year,
                timeDate.tm_mon,
                timeDate.tm_mday,
                timeTime.tm_hour,
                timeTime.tm_min,
                timeTime.tm_sec,
                timeDate.tm_wday,
                timeDate.tm_yday,
                -1))

# argparser is messy. Put it in a function,
# so we can export it to another file if we want to.
def parseArgs():

    # initiate an argParser object
    argParser = argparse.ArgumentParser(prog="logsnapper.py"
            ,description="Extract a snapshot from logfiles, centered around a specified time/date.")

    # define a first argument, date
    argParser.add_argument("date",
            type=parseTime,
            help="a date, expressed as YYYY-MM-DD")

    # define an optional argument, time, that is set to time 12:00:00 if not specified
    argParser.add_argument("time"
            ,type=parseTime
            ,nargs='?'
            ,default=parseTime("12:00:00")
            ,help="a time, expressed as HH:MM:SS, using 24-hour clock"
            )

    # define an optional argument, timespan, that defaults to 12 hours
    argParser.add_argument("-s,--span"
            ,type=float
            ,nargs='?'
            ,default=12
            ,dest='timespan'
            ,help="number of hours before and after the given time to include in the results. May be decimal."
            ,metavar="TIMESPAN"
            )

    # define an optional argument, files
    argParser.add_argument("-f,--files"
            ,type=parsePath
            ,nargs='+'
            ,dest='logFilePaths'
            ,help="additional files to search through"
            ,metavar=("FILE","FILES")
            )

    # fire up the argument parser
    return(argParser.parse_args())

# start of main script

args = parseArgs()

# initiate the list of standard logfiles to search in
logFiles = []

for stdLogFile in stdLogFiles:
    logFiles.append(file(stdLogFile))

# add any new files from the commandline arguments
# skip files that we can't read, and skip directories
# TODO: remove binary files
for argLogPath in args.logFilePaths:
    if os.path.isfile(argLogPath):
        try:
            fp = open(argLogPath)
            if not fp.name in (logFile.name for logFile in logFiles):
                logFiles.append(fp)
        except IOError as e:
            if e.errno == errno.EACCES:
                print "skipping %s - permission denied" % argLogPath
    elif  os.path.isdir(argLogPath):
        print "skipping %s - is a directory" % argLogPath

# get the exact time we're after
dateTime = joinTime(args.date,args.time)

# transmute the timespan to seconds
timeSpan = int(args.timespan * 3600)

outLines=[]
lineTime=time.localtime()
# plow through the files, line by line, and extract times according to a couple of normal rsyslog formats.
# TODO: see if we can't make the lines skip/jumpable, so we can check n lines in advance, and double back if we've hit the window
for logFile in logFiles:
    for line in logFile:
        print lineTime
        # there's a couple of different time formats in logfiles
        # but all fields are space-separated, so we'll split the line
        splitLine = line.split(' ',5);
        # now see if we can find a time format in the line, using a couple of different methods
        # TODO: remove binary lines, if we can't remove binary files earlier
        # this one is the most common one. it's rsyslog's local Locale format.
        try:
            lineTime = time.strptime("%s %s %s %s" % (time.gmtime()[0], splitLine[0], splitLine[1], splitLine[2]),'%Y %b %d %X')
        except:
            # dpkg uses a different format, which includes the year
            try:
                lineTime = time.strptime("%s %s" % (splitLine[0], splitLine[1]),'%Y-%m-%d %H:%M:%S')
            except:
                # and I've also seen the same one, but with a application name in front
                try:
                    lineTime = time.strptime("%s %s" % (splitLine[1], splitLine[2]),'%Y-%m-%d %H:%M:%S')
                except:
                    continue
        # convert the time_struct into seconds, so we can compare it
        lineTime = time.mktime(lineTime)
        # and check if the line's time is within our target window
        if (dateTime - timeSpan) <= lineTime and lineTime <= (dateTime + timeSpan):
            # Add the line in our to-print-list. Start with the time, as seconds, for sorting.
            # Then put the filename, and last the line, with its trailing newline removed.
            outLines.append((lineTime,logFile.name,line.rstrip('\n')))
        # reset the line's time to outside of the span
        lineTime = dateTime - timeSpan - 1

# sort the lines, according to the first field
outLines.sort(cmp=lambda x,y: cmp(x[0],y[0]))

# now print the lines, prepended by their filenames 
for line in outLines:
    print "%s: %s" % (line[1], line[2])
