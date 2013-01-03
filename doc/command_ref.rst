#######################
 DNF Command Reference
#######################

========
Synopsis
========

``dnf [options] <command> [<args>...]``

===========
Description
===========

`DNF`_ is an experimental replacement for `Yum`_, a package manager for RPM Linux
distributions. It aims to maintain CLI compatibility with Yum while improving on
speed and defining strict API and plugin interface.

Available commands are:

* check-update
* clean
* dist-sync
* distribution-sync
* downgrade
* erase
* help
* history
* info
* install
* list
* makecache
* provides
* reinstall
* repolist
* search
* update
* update-to
* upgrade
* upgrade-to

See the reference for each command below.

=======
Options
=======

``-h, --help``
    Shows the help.

``-C, --cacheonly``
    Run entirely from system cache, don't update cache

``-c <config file>, --config=<config file>``
    config file location

``-R <minutes>, --randomwait=<minutes>``
    maximum command wait time

``-d <debug level>, --debuglevel=<debug level>``
    debugging output level

``-x <package-spec>, --exclude=<package-spec>``
    Exclude packages specified by a name or a glob from the operation.

``--showduplicates``
    show duplicates, in repos, in list/search commands

``-e <error level>, --errorlevel=<error level>``
    error output level

``--rpmverbosity=<debug level name>``
    debugging output level for rpm

``-q, --quiet``
    quiet operation

``-v, --verbose``
    verbose operation

``-y, --assumeyes``
    answer yes for all questions

``--assumeno``
    answer no for all questions

``--version``
    show Yum version and exit

``--installroot=<path>``
    set install root

========
Commands
========

For an explanation of ``<package-spec>`` see :ref:`\specifying_packages-label`.

For an explanation of ``<package-nevr-spec>`` see :ref:`\specifying_packages_versions-label`.

For an explanation of ``<provide-spec>`` see :ref:`\specifying_provides-label`.

--------------------
Check Update Command
--------------------

``dnf [options] check-update [<package-specs>...]``

    Non-interactively checks if updates of the specified packages are
    available. If no ``<package-specs>`` are given checks whether any updates at
    all are available for your system. DNF exit code will be 100 when there are
    updates available and a list of the updates will be printed, 0 if not and 1
    if an error occurs.

-------------
Clean Command
-------------
Performs cleanup of temporary files for the currently enabled repositories.

``dnf clean dbcache``
    Removes cache files generated from the repository metadata. This forces DNF
    to regenerate the cache files the next time it is run.

``dnf clean expire-cache``
    Removes local cookie files saying when the metadata and mirrorlists were
    downloaded for each repo. DNF will re-validate the cache for each repo the
    next time it is used.

``dnf clean metadata``
    Removes repository metadata. Those are the files which DNF uses to determine
    the remote availability of packages. Using this option will make DNF
    download all the metadata the next time it is run.

``dnf clean packages``
    Removes any cached packages from the system.  Note that packages are not
    automatically deleted after they are downloaded.

``dnf clean plugins``
    Tells all enabled plugins to eliminate their cached data.

``dnf clean all``
    Does all of the above.

.. _dist_sync_command-label:

-----------------
Dist-sync command
-----------------
``dnf dist-sync``
    As necessary upgrades, downgrades or keeps all installed packages to match
    the latest version available from any enabled repository.

-------------------------
Distribution-sync command
-------------------------
    Deprecated alias for the :ref:`\dist_sync_command-label`.

-----------------
Downgrade Command
-----------------
``dnf [options] downgrade <package-specs>...``
    Downgrades the specified packages to the highest of all known lower versions.

-------------
Erase Command
-------------
``dnf [options] erase <package-specs>...``
    Removes the specified packages from the system along with any packages
    depending on the packages being removed. If ``clean_requirements_on_remove``
    is enabled also removes any dependencies that are no longer needed.

------------
Help Command
------------

``dnf help [<command>]``
    Displays the help text for all commands. If given a command name then only
    displays the help for that particular command.

---------------
History Command
---------------

The history command allows the user to view what has happened in past
transactions (assuming the ``history_record`` configuration option is set).

``dnf history [list]``
    The default history action is listing all known transaction information in a
    table.

``dnf history info [<transaction_id>]``
    Describe the given transaction. When no ID is given describes what happened
    during the latest transaction.

------------
Info Command
------------

``dnf [options] info <package-specs>...``
    Is used to list a description and summary information about available packages.

---------------
Install Command
---------------
``dnf [options] install <package-specs>...``
    Installs the specified packages and their dependencies. After the
    transaction is finished all the specified packages are installed on the
    system.

------------
List Command
------------

Dumps lists of packages depending on the packages' relation to the
system. Generally packages are available (it is present in a repository we know
about) or installed (present in the RPMDB). The list command can also limit the
displayed packages according to other criteria, e.g. to only those that update
an installed package.

All the forms take a ``[<package-specs>...]`` parameter to further limit the
result to only those packages matching it.

``dnf [options] list [all] [<package-specs>...]``
    Lists all packages known to us, present in the RPMDB, in a repo or in both.

``dnf [options] list installed [<package-specs>...]``
    Lists installed packages.

``dnf [options] list available [<package-specs>...]``
    Lists available packages.

``dnf [options] list extras [<package-specs>...]``
    Lists extras, that is packages installed on the system that are not
    available in any known repository.

``dnf [options] list obsoletes [<package-specs>...]``
    List the packages installed on the system that are obsoleted by packages in
    any known repository.

-----------------
Makecache Command
-----------------
``dnf [options] makecache``
    Downloads and caches in binary format metadata for all known repos. Tries to
    avoid downloading whenever possible (typically when the metadata timestamp
    hasn't changed).

----------------
Provides Command
----------------
``dnf [options] provides <provide-spec>``
    Finds the packages providing the given ``<provide-spec>``. This is useful
    when one knows a filename and wants to find what package (installed or not)
    provides this file.

-----------------
Reinstall Command
-----------------
``dnf [options] reinstall <package-specs>...``
    Installs the specified packages, fails if some of the packages are either
    not installed or not available (i.e. there is no repository where to
    download the same RPM).

----------------
Repolist Command
----------------
``dnf [options] repolist [enabled|disabled|all]``
    Depending on the exact command, lists enabled, disabled or all known
    repositories. Lists all enabled repositories by default. Provides more
    detailed information when ``-v`` option is used.

--------------
Search Command
--------------
``dnf [options] search [all] <keywords>...``
    Search package metadata for the keywords. Keywords are matched as
    case-sensitive substrings, globbing is supported. By default the command
    will only look at package names and summaries, failing that (or whenever
    ``all`` was given as an argument) it will match against package descriptions
    and URLs. The result is sorted from the most relevant results to the least.

--------------
Update Command
--------------
    Deprecated alias for the :ref:`\upgrade_command-label`.

.. _upgrade_command-label:

---------------
Upgrade Command
---------------
``dnf [options] upgrade``
    Updates each package to a highest version that is both available and
    resolvable.

``dnf [options] upgrade <package-specs>...``
    Updates each specified package to the latest available version. Updates
    dependencies as necessary.

-----------------
Update-To Command
-----------------
    Deprecated alias for the :ref:`\upgrade_to_command-label`.

.. _upgrade_to_command-label:

------------------
Upgrade-To Command
------------------
``dnf [options] upgrade-to <package-nevr-specs>...``
    Upgrades packages to the specified versions.

.. _specifying_packages-label:

===================
Specifying Packages
===================

Many commands take a ``<package-spec>`` parameter that selects a package for the
operation. DNF looks for interpretations of ``<package-spec>`` from the most
specific meanings to the least, that is it first tries to see if the spec could
mean a full ``name-[epoch:]version-release.arch`` specification, then just
``name-[epoch:]version-release``, ``name.arch``, just name and finally
``name-version``. ``name-version`` is generally not more specific than ``name``,
because many package names contain the dash and version can be a string of
almost arbitrary characters: this would cause DNF to first interpret
``name-subname`` as ``name`` in version ``subname`` instead of looking for a
package called ``name-subname``.

If multiple versions of the selected package exist in the repo, the most recent
version suitable for the given operation is used.  The name specification is
case-sensitive, globbing characters "``?``, ``*`` and ``[`` are allowed and
trigger shell-like glob matching.

.. _specifying_packages_versions-label:

=====================================
Specifying Exact Versions of Packages
=====================================

Commands accepting the ``<package-nevr-spec>`` parameter need not only the name
of the package, but also its version, release and optionally the
architecture. Further, the version part can be preceded by an epoch when it is
relevant (i.e. the epoch is non-zero).

.. _specifying_provides-label:

===================
Specifying Provides
===================

``<provide-spec>`` in command descriptions means the command operates on
packages providing the given spec. This can either be an explicit provide, an
implicit provide (i.e. name of the package) or a file provide. The selection is
case-sensitive and globbing is supported.

========
See Also
========

* `DNF`_ project homepage (https://github.com/akozumpl/dnf/)
* `Yum`_ project homepage (http://yum.baseurl.org/)
