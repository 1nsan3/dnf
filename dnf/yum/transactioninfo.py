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
# Copyright 2005 Duke University
# Written by Seth Vidal

# TODOS: make all the package relationships deal with package objects
# search by package object for TransactionData, etc.
# provide a real TransactionData.remove(txmbr) method, It should
# remove the given txmbr and iterate to remove all those in depedent relationships
# with the given txmbr.

"""
Classes and functions for manipulating a transaction to be passed
to rpm.
"""

from constants import *
from packages import YumInstalledPackage
import Errors
import warnings
import misc

import hawkey

class TransactionData:
    """Data Structure designed to hold information on a yum Transaction Set"""
    def __init__(self, prob_filter_flags=None):
        self.flags = []
        self.vsflags = []
        self.probFilterFlags = []
        if prob_filter_flags:
            self.probFilterFlags = prob_filter_flags[:]
        self.root = '/'
        self.pkgdict = {} # key = pkgtup, val = list of TransactionMember obj
        self._namedict = {} # name -> list of TransactionMember obj
        self._unresolvedMembers = set()
        self.debug = 0
        self.changed = False
        self.installonlypkgs = []
        self.state_counter = 0
        self.conditionals = {} # key = pkgname, val = list of pos to add

        self.rpmdb = None
        self.pkgSack = None
        self.pkgSackPackages = 0
        self._inSack = None

        # lists of txmbrs in their states - just placeholders
        self.instgroups = []
        self.removedgroups = []
        self.removed = []
        self.installed = []
        self.updated = []
        self.obsoleted = []
        self.depremoved = []
        self.depinstalled = []
        self.depupdated = []
        self.reinstalled = []
        self.downgraded = []
        self.failed = []
        self.selector_installs = []
        self.upgrade_all = False

    def __len__(self):
        return len(self.pkgdict) + len(self.selector_installs)

    def __iter__(self):
        if hasattr(self.getMembers(), '__iter__'):
            return self.getMembers().__iter__()
        else:
            return iter(self.getMembers())

    def debugprint(self, msg):
        if self.debug:
            print msg

    def getMembersWithState(self, pkgtup=None, output_states=None):
        return filter(lambda p: p.output_state in output_states,
                      self.getMembers(pkgtup))

    def getMembers(self, pkgtup=None):
        """takes an optional package tuple and returns all transaction members
           matching, no pkgtup means it returns all transaction members"""

        returnlist = []

        if pkgtup is None:
            for members in self.pkgdict.itervalues():
                returnlist.extend(members)
        elif pkgtup in self.pkgdict:
            returnlist.extend(self.pkgdict[pkgtup])
        return returnlist

    # The order we resolve things in _matters_, so for sanity sort the list
    # otherwise .i386 can be different to .x86_64 etc.
    def getUnresolvedMembers(self):
        return list(sorted(self._unresolvedMembers))

    def markAsResolved(self, txmbr):
        self._unresolvedMembers.discard(txmbr)

    def resetResolved(self, hard=False):
        if hard or len(self) < len(self._unresolvedMembers):
            self._unresolvedMembers.clear()
            self._unresolvedMembers.update(self.getMembers())
            return True
        return False

    def getMode(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the mode of the first match from the transaction set,
           otherwise, returns None"""

        txmbrs = self.matchNaevr(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)
        if not len(txmbrs):
            return None
        states = []
        for txmbr in txmbrs:
            states.append(txmbr.ts_state)

        if 'u' in states:
            return 'u'
        elif 'i' in states:
            return 'i'
        else:
            return states[0]

    def matchNaevr(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the list of packages matching the args above"""
        if name is None:
            txmbrs = self.getMembers()
        else:
            txmbrs = self._namedict.get(name, [])
            if arch is None and epoch is None and ver is None and rel is None:
                return txmbrs[:]

        result = []

        for txmbr in txmbrs:
            (n, a, e, v, r) = txmbr.pkgtup
            # Name is done above
            if arch is not None and arch != a:
                continue
            if epoch is not None and epoch != e:
                continue
            if ver is not None and ver != v:
                continue
            if rel is not None and rel != r:
                continue
            result.append(txmbr)

        return result

    def deselect(self, pattern):
        """ Remove these packages from the transaction. This is more user
            orientated than .remove(). Used from kickstart/install -blah. """

        #  We don't have a returnPackages() here, so just try the "simple"
        # specifications. Pretty much 100% hit rate on kickstart.
        txmbrs = self.matchNaevr(pattern)
        if not txmbrs:
            na = pattern.rsplit('.', 2)
            if len(na) == 2:
                txmbrs = self.matchNaevr(na[0], na[1])

        if not txmbrs:
            if self.pkgSack is None:
                pkgs = []
            else:
                pkgs = self.pkgSack.returnPackages(patterns=[pattern])
            if not pkgs:
                pkgs = self.rpmdb.returnPackages(patterns=[pattern])

            for pkg in pkgs:
                txmbrs.extend(self.getMembers(pkg.pkgtup))
                #  Now we need to do conditional group packages, so they don't
                # get added later on. This is hacky :(
                for req, cpkgs in self.conditionals.iteritems():
                    if pkg in cpkgs:
                        cpkgs.remove(pkg)
                        self.conditionals[req] = cpkgs

        for txmbr in txmbrs:
            self.remove(txmbr.pkgtup)
        return txmbrs

    def _allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""

        if po.name in self.installonlypkgs:
            return True
        return False # :hawkey

        provides = po.provides_names
        if filter (lambda prov: prov in self.installonlypkgs, provides):
            return True

        return False

    def add(self, txmember):
        """add a package to the transaction"""

        if txmember.pkgtup not in self.pkgdict:
            self.pkgdict[txmember.pkgtup] = []
        else:
            self.debugprint("Package: %s.%s - %s:%s-%s already in ts" % txmember.pkgtup)
            for member in self.pkgdict[txmember.pkgtup]:
                if member.ts_state == txmember.ts_state:
                    self.debugprint("Package in same mode, skipping.")
                    return
        self.pkgdict[txmember.pkgtup].append(txmember)
        self._namedict.setdefault(txmember.name, []).append(txmember)
        self.changed = True
        self.state_counter += 1
        if self._inSack is not None and txmember.output_state in TS_INSTALL_STATES:
            if not txmember.po.have_fastReturnFileEntries():
                # In theory we could keep this on if a "small" repo. fails
                self._inSack = None
            else:
                self._inSack.addPackage(txmember.po)

        if txmember.name in self.conditionals:
            for pkg in self.conditionals[txmember.name]:
                if self.rpmdb.contains(po=pkg):
                    continue
                for condtxmbr in self.install_method(po=pkg):
                    condtxmbr.setAsDep(po=txmember.po)

        self._unresolvedMembers.add(txmember)

    def remove(self, pkgtup):
        """remove a package from the transaction"""
        if pkgtup not in self.pkgdict:
            self.debugprint("Package: %s not in ts" %(pkgtup,))
            return
        for txmbr in self.pkgdict[pkgtup]:
            txmbr.po.state = None
            if self._inSack is not None and txmbr.output_state in TS_INSTALL_STATES:
                self._inSack.delPackage(txmbr.po)
            self._namedict[txmbr.name].remove(txmbr)
            self._unresolvedMembers.add(txmbr)

        del self.pkgdict[pkgtup]
        if not self._namedict[pkgtup[0]]:
            del self._namedict[pkgtup[0]]
        self.changed = True
        self.state_counter += 1

    def exists(self, pkgtup):
        """tells if the pkg is in the class"""
        if pkgtup in self.pkgdict:
            if len(self.pkgdict[pkgtup]) != 0:
                return 1

        return 0

    def makelists(self, include_reinstall=False, include_downgrade=False):
        """returns lists of transaction Member objects based on mode:
           updated, installed, erased, obsoleted, depupdated, depinstalled
           deperased"""

        self.instgroups = []
        self.removedgroups = []
        self.removed = []
        self.installed = []
        self.updated = []
        self.obsoleted = []
        self.depremoved = []
        self.depinstalled = []
        self.depupdated = []
        self.reinstalled = []
        self.downgraded = []
        self.failed = []

        for txmbr in self.getMembers():
            if txmbr.output_state == TS_UPDATE:
                if txmbr.isDep:
                    self.depupdated.append(txmbr)
                else:
                    self.updated.append(txmbr)

            elif txmbr.output_state in (TS_INSTALL, TS_TRUEINSTALL):
                if include_reinstall and txmbr.reinstall:
                    self.reinstalled.append(txmbr)
                    continue

                if include_downgrade and txmbr.downgrades:
                    self.downgraded.append(txmbr)
                    continue

                if txmbr.groups:
                    for g in txmbr.groups:
                        if g not in self.instgroups:
                            self.instgroups.append(g)
                if txmbr.isDep:
                    self.depinstalled.append(txmbr)
                else:
                    self.installed.append(txmbr)

            elif txmbr.output_state == TS_ERASE:
                if include_downgrade and txmbr.downgraded_by:
                    continue

                for g in txmbr.groups:
                    if g not in self.instgroups:
                        self.removedgroups.append(g)
                if txmbr.isDep:
                    self.depremoved.append(txmbr)
                else:
                    self.removed.append(txmbr)

            elif txmbr.output_state == TS_OBSOLETED:
                self.obsoleted.append(txmbr)

            elif txmbr.output_state == TS_OBSOLETING:
                self.installed.append(txmbr)
            elif txmbr.output_state == TS_FAILED:
                self.failed.append(txmbr)

            else:
                pass

        self.updated.sort()
        self.installed.sort()
        self.removed.sort()
        self.obsoleted.sort()
        self.depupdated.sort()
        self.depinstalled.sort()
        self.depremoved.sort()
        self.instgroups.sort()
        self.removedgroups.sort()
        self.reinstalled.sort()
        self.downgraded.sort()
        self.failed.sort()

    def addInstall(self, po):
        """adds a package as an install but in mode 'u' to the ts
           takes a packages object and returns a TransactionMember Object"""

        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_INSTALL
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'i'
        self.add(txmbr)
        return txmbr # :hawkey

        if self.rpmdb.contains(po=txmbr.po):
            txmbr.reinstall = True

        self.add(txmbr)
        return txmbr

    def add_selector_install(self, sltr):
        self.selector_installs.append(sltr)

    def addTrueInstall(self, po):
        """adds a package as an install
           takes a packages object and returns a TransactionMember Object"""

        return self.addInstall(po) # :hawkey
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_TRUEINSTALL
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'i'

        if self.rpmdb.contains(po=txmbr.po):
            txmbr.reinstall = True

        self.add(txmbr)
        return txmbr


    def addErase(self, po):
        """adds a package as an erasure
           takes a packages object and returns a TransactionMember Object"""

        txmbr = TransactionMember(po)
        txmbr.current_state = TS_INSTALL
        txmbr.output_state = TS_ERASE
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'e'
        self.add(txmbr)
        return txmbr

    def addUpdate(self, po, oldpo=None):
        """adds a package as an update
           takes a packages object and returns a TransactionMember Object"""

        if self._allowedMultipleInstalls(po):
            return self.addTrueInstall(po)

        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_UPDATE
        txmbr.po.state = TS_UPDATE
        txmbr.ts_state = 'u'
        if oldpo:
            txmbr.relatedto.append((oldpo, 'updates'))
            txmbr.updates.append(oldpo)
            self._addUpdated(oldpo, po)

        self.add(txmbr)
        return txmbr

    def addDowngrade(self, po, oldpo=None):
        """adds a package as an downgrade takes a packages object and returns
           a pair of TransactionMember Objects"""

        atxmbr = self.addInstall(po)

        if oldpo:
            itxmbr = self.addErase(oldpo)
            itxmbr.relatedto.append((po, 'downgradedby'))
            itxmbr.downgraded_by.append(po)
            atxmbr.relatedto.append((oldpo, 'downgrades'))
            atxmbr.downgrades.append(oldpo)
        return atxmbr

    # deprecated
    def _addUpdated(self, po, updating_po):
        """adds a package as being updated by another pkg
           takes a packages object and returns a TransactionMember Object

           :hawkey: no point exposing this function on the interface.
        """

        txmbr = TransactionMember(po)
        txmbr.current_state = TS_INSTALL
        txmbr.output_state =  TS_UPDATED
        txmbr.po.state = TS_UPDATED
        txmbr.ts_state = 'ud'
        txmbr.relatedto.append((updating_po, 'updatedby'))
        txmbr.updated_by.append(updating_po)
        self.add(txmbr)
        return txmbr

class SortableTransactionData(TransactionData):
    """A transaction data implementing topological sort on it's members"""
    def __init__(self):
        # Cache of sort
        self._sorted = []
        # Current dependency path
        self.path = []
        # List of loops
        self.loops = []
        TransactionData.__init__(self)

    def _visit(self, txmbr):
        self.path.append(txmbr.name)
        txmbr.sortColour = TX_GREY
        for po in txmbr.depends_on:
            vertex = self.getMembers(pkgtup=po.pkgtup)[0]
            if vertex.sortColour == TX_GREY:
                self._doLoop(vertex.name)
            if vertex.sortColour == TX_WHITE:
                self._visit(vertex)
        txmbr.sortColour = TX_BLACK
        self._sorted.insert(0, txmbr.pkgtup)

    def _doLoop(self, name):
        self.path.append(name)
        loop = self.path[self.path.index(self.path[-1]):]
        if len(loop) > 2:
            self.loops.append(loop)

    def add(self, txmember):
        txmember.sortColour = TX_WHITE
        TransactionData.add(self, txmember)
        self._sorted = []

    def remove(self, pkgtup):
        TransactionData.remove(self, pkgtup)
        self._sorted = []

    def sort(self):
        if self._sorted:
            return self._sorted
        self._sorted = []
        # loop over all members
        for txmbr in self.getMembers():
            if txmbr.sortColour == TX_WHITE:
                self.path = [ ]
                self._visit(txmbr)
        self._sorted.reverse()
        return self._sorted


class TransactionMember:
    """Class to describe a Transaction Member (a pkg to be installed/
       updated/erased)."""

    def __init__(self, po):
        # holders for data
        self.po = po # package object
        self.current_state = None # where the package currently is (repo, installed)
        self.ts_state = None # what state to put it into in the transaction set
        self.output_state = None # what state to list if printing it
        self.isDep = 0
        self.reason = 'unknown' # reason for it to be in the transaction set
        self.process = None #  I think this is used nowhere by nothing - skv 2010/11/03
        self.relatedto = [] # ([relatedpkg, relationship)]
        self.depends_on = []
        self.obsoletes = []
        self.obsoleted_by = []
        self.updates = []
        self.updated_by = []
        self.downgrades = []
        self.downgraded_by = []
        self.reinstall = False
        self.groups = [] # groups it's in
        self._poattr = ['pkgtup', 'reponame', 'name', 'arch', 'evr']

        for attr in self._poattr:
            val = getattr(self.po, attr)
            setattr(self, attr, val)

        return # :hawkey
        if po.from_system:
            #  We want to load these so that we can auto hardlink in the same
            # new values. Because of the hardlinks it should be really cheap
            # to load them ... although it's still a minor hack.
            po.yumdb_info.get('from_repo')
            po.yumdb_info.get('releasever')
            po.yumdb_info.get('changed_by')

    def setAsDep(self, po=None):
        """sets the transaction member as a dependency and maps the dep into the
           relationship list attribute"""

        self.isDep = 1
        if po:
            self.relatedto.append((po, 'dependson'))
            self.depends_on.append(po)

    def __cmp__(self, other):
        return cmp(self.po, other.po)

    def __hash__(self):
        return object.__hash__(self)

    def __str__(self):
        return "%s.%s %s - %s" % (self.name, self.arch, self.evr,
                                  self.ts_state)

    def __repr__(self):
        return "<%s : %s (%s)>" % (self.__class__.__name__, str(self),hex(id(self)))

    def _dump(self):
        msg = "mbr: %s,%s,%s,%s,%s %s\n" % (self.name, self.arch, self.epoch,
                     self.version, self.release, self.current_state)
        msg += "  repo: %s\n" % self.po.repo.id
        msg += "  ts_state: %s\n" % self.ts_state
        msg += "  output_state: %s\n" %  self.output_state
        msg += "  isDep: %s\n" %  bool(self.isDep)
        msg += "  reason: %s\n" % self.reason
        #msg += "  process: %s\n" % self.process
        msg += "  reinstall: %s\n" % bool(self.reinstall)

        if self.relatedto:
            msg += "  relatedto:"
            for (po, rel) in self.relatedto:
                pkgorigin = 'a'
                if isinstance(po, YumInstalledPackage):
                    pkgorigin = 'i'
                msg += " %s,%s,%s,%s,%s@%s:%s" % (po.name, po.arch, po.epoch,
                      po.version, po.release, pkgorigin, rel)
            msg += "\n"

        for lst in ['depends_on', 'obsoletes', 'obsoleted_by', 'downgrades',
                    'downgraded_by', 'updates', 'updated_by']:
            thislist = getattr(self, lst)
            if thislist:
                msg += "  %s:" % lst
                for po in thislist:
                    pkgorigin = 'a'
                    if isinstance(po, YumInstalledPackage):
                        pkgorigin = 'i'
                    msg += " %s,%s,%s,%s,%s@%s" % (po.name, po.arch, po.epoch,
                        po.version, po.release, pkgorigin)
                msg += "\n"

        if self.groups:
            msg += "  groups: %s\n" % ' '.join(self.groups)

        return msg

    def propagated_reason(self, yumdb):
        if self.reason == "user":
            return self.reason
        previously = None
        if self.updates:
            updated = self.updates[0]
            previously =  yumdb.get_package(updated).get('reason')
        elif self.downgrades:
            downgraded = self.downgrades[0]
            previously = yumdb.get_package(downgraded).get('reason')
        if previously:
            return previously
        return self.reason
