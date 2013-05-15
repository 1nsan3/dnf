# Copyright 2005 Duke University
# Copyright (C) 2012-2013  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Entrance point for the yum command line interface.
"""

from __future__ import print_function
import os
import os.path
import sys
import logging
import time
import errno

import dnf.exceptions
from dnf.yum import plugins
from dnf.yum.i18n import utf8_width, exception2msg, _
import dnf.i18n
import dnf.cli.cli
from utils import suppress_keyboard_interrupt_message, show_lock_owner

def main(args):
    """Run the yum program from a command line interface."""

    dnf.i18n.setup_locale()
    dnf.i18n.setup_stdout()

    def exUserCancel():
        logger.critical(_('Terminated.'))
        if unlock(): return 200
        return 1

    def exIOError(e):
        if e.errno == 32:
            logger.critical(_('Exiting on Broken Pipe'))
        else:
            logger.critical(exception2msg(e))
        if unlock(): return 200
        return 1

    def exPluginExit(e):
        '''Called when a plugin raises PluginYumExit.

        Log the plugin's exit message if one was supplied.
        '''
        exitmsg = exception2msg(e)
        if exitmsg:
            logger.warn('%s', exitmsg)
        return 200 if unlock() else 1

    def exFatal(e):
        if e.value is not None:
            logger.critical(exception2msg(e.value))
        return 200 if unlock() else 1

    def unlock():
        try:
            base.closeRpmDB()
            base.doUnlock()
        except dnf.exceptions.LockError, e:
            return 200
        return 0

    logger = logging.getLogger("dnf")

    # our core object for the cli
    base = dnf.cli.cli.YumBaseCli()
    base.logging.presetup()
    cli = dnf.cli.cli.Cli(base)

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        cli.configure(args)
        cli.check()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except dnf.exceptions.Error, e:
        return exFatal(e)

    # Try to open the current directory to see if we have
    # read and execute access. If not, chdir to /
    try:
        f = open(".")
    except IOError, e:
        if e.errno == errno.EACCES:
            logger.critical(_('No read/execute access in current directory, moving to /'))
            os.chdir("/")
    else:
        f.close()

    lockerr = ""
    while True:
        try:
            base.doLock()
        except dnf.exceptions.LockError, e:
            if exception2msg(e) != lockerr:
                lockerr = exception2msg(e)
                logger.critical(lockerr)
            if e.errno in (errno.EPERM, errno.EACCES, errno.ENOSPC):
                logger.critical(_("Can't create lock file; exiting"))
                return 1

            if not base.conf.exit_on_lock:
                logger.critical(_("Another app is currently holding the yum lock; waiting for it to exit..."))
                tm = 0.1
                if show_lock_owner(e.pid, logger):
                    tm = 2
                time.sleep(tm)
            else:
                logger.critical(_("Another app is currently holding the yum lock; exiting as configured by exit_on_lock"))
                return 1
        else:
            break

    try:
        result, resultmsgs = cli.run()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except dnf.exceptions.Error, e:
        result = 1
        resultmsgs = [exception2msg(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    # Act on the command/shell result
    if result == 0:
        # Normal exit
        for msg in resultmsgs:
            logger.info('%s', msg)
        if unlock(): return 200
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical(_('Error: %s'), msg)
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    elif result == 100:
        if unlock(): return 200
        return 100
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3

    # Depsolve stage
    logger.info(_('Resolving Dependencies'))

    try:
        (result, resultmsgs) = base.build_transaction()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except dnf.exceptions.Error, e:
        result = 1
        resultmsgs = [exception2msg(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    # Act on the depsolve result
    if result == 0:
        # Normal exit
        if unlock(): return 200
        for msg in resultmsgs:
            print(msg)
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            prefix = _('Error: %s')
            prefix2nd = (' ' * (utf8_width(prefix) - 2))
            logger.critical(prefix, msg.replace('\n', '\n' + prefix2nd))
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3

    logger.info(_('\nDependencies Resolved'))

    # Run the transaction
    try:
        return_code = base.doTransaction()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except dnf.exceptions.Error, e:
        return exFatal(e)
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    # rpm ts.check() failed.
    if type(return_code) == type((0,)) and len(return_code) == 2:
        (result, resultmsgs) = return_code
        for msg in resultmsgs:
            logger.critical("%s", msg)
        return_code = result
        if base._ts_save_file:
            logger.info(_("Your transaction was saved, rerun it with:\n yum load-transaction %s") % base._ts_save_file)
    elif return_code < 0:
        return_code = 1 # Means the pre-transaction checks failed...
        #  This includes:
        # . No packages.
        # . Hitting N at the prompt.
        # . GPG check failures.
        if base._ts_save_file:
            logger.info(_("Your transaction was saved, rerun it with:\n yum load-transaction %s") % base._ts_save_file)
    else:
        logger.info(_('Complete!'))

    if unlock(): return 200
    return return_code

def hotshot(func, *args, **kwargs):
    """Profile the given function using the hotshot profiler.

    :param func: the function to profile
    :return: the return code given by the hotshot profiler
    """
    import hotshot.stats
    fn = os.path.expanduser("~/yum.prof")
    prof = hotshot.Profile(fn)
    rc = prof.runcall(func, *args, **kwargs)
    prof.close()
    print_stats(hotshot.stats.load(fn))
    return rc

def cprof(func, *args, **kwargs):
    """Profile the given function using the cprof profiler.

    :param func: the function to profile
    :return: the return code given by the cprof profiler
    """
    import cProfile, pstats
    fn = os.path.expanduser("~/yum.prof")
    prof = cProfile.Profile()
    rc = prof.runcall(func, *args, **kwargs)
    prof.dump_stats(fn)
    print_stats(pstats.Stats(fn))
    return rc

def print_stats(stats):
    """Print out information from a :class:`Stats` object.

    :param stats: the :class:`Stats` object to print information from
    """
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)
    stats.sort_stats('cumulative')
    stats.print_stats(40)

def user_main(args, exit_code=False):
    """Call one of the multiple main() functions based on environment variables.

    :param args: command line arguments passed into yum
    :param exit_code: if *exit_code* is True, this function will exit
       python with its exit code when it has finished executing.
       Otherwise, it will return its exit code.
    :return: the exit code from dnf.yum execution
    """
    errcode = None
    if 'YUM_PROF' in os.environ:
        if os.environ['YUM_PROF'] == 'cprof':
            errcode = cprof(main, args)
        if os.environ['YUM_PROF'] == 'hotshot':
            errcode = hotshot(main, args)
    if 'YUM_PDB' in os.environ:
        import pdb
        pdb.run(main(args))

    if errcode is None:
        errcode = main(args)
    if exit_code:
        sys.exit(errcode)
    return errcode

suppress_keyboard_interrupt_message()

if __name__ == "__main__":
    try:
        user_main(sys.argv[1:], exit_code=True)
    except KeyboardInterrupt, e:
        print(_("\n\nExiting on user cancel."), file=sys.stderr)
        sys.exit(1)
