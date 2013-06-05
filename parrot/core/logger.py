# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

########################################################################
# Copyright (c) 2013 Ericsson AB
# 
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v10.html
# 
# Contributors:
#    Ericsson Research - initial implementation
#
########################################################################

import datetime
import sqlite3 as lite

class Logger:

    def __init__(self, logfile="/tmp/parrotlogger.db"):
        self.conn = lite.connect(logfile)
        self.cur = self.conn.cursor()
        self.cur.execute("DROP TABLE IF EXISTS Logger")
        self.cur.execute("CREATE TABLE Logger(Timestamp INT, Urn TEXT, Category TEXT, Msg TEXT)")

    def close(self):
        self.conn.close()

    def setlog(self, urn, msg, category=''):
        log = (int(datetime.datetime.now().strftime("%s"))*1000, str(urn), category, msg)
        self.cur.execute("INSERT INTO Logger VALUES(?, ?, ?, ?)", log)
        self.conn.commit()


    def getlog(self, urn_filter=None, category_filter=None, timestamp_filter=None, msg_filter=None):
        """Get a list of events from the log database. Optionally filtered using 
        <col> LIKE <filter>, where filter is an sqlite regexp with '%', '_', '[<range>]'
        The return value is a list (possibly empty) with a dict for each row.""" 

        qstr = ['timestamp', 'urn', 'category', 'msg']
        prop = [timestamp_filter, urn_filter, category_filter, msg_filter]
        filter = []
        filter_params = ()
        query = ''
        for q, p in zip(qstr, prop):
            if not p:
                continue
            filter.append('%s LIKE ?'%q)    
            relaxed_param = '%'+p+'%'
            filter_params += (relaxed_param,)
        
        if filter:
            query = ' WHERE ' + ' AND '.join(filter)

        result = self.cur.execute('SELECT * FROM Logger'+query, filter_params)

        retval = []
        for row in result:
            retval.append(dict(zip(qstr, row)))
            
        return retval    
