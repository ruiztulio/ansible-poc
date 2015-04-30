#!/usr/bin/env python
# (C) 2012, Michael DeHaan, <michael.dehaan@gmail.com>

# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

#######################################################

__requires__ = ['ansible']
try:
    import pkg_resources
except Exception:
    # Use pkg_resources to find the correct versions of libraries and set
    # sys.path appropriately when there are multiversion installs.  But we
    # have code that better expresses the errors in the places where the code
    # is actually used (the deps are optional for many code paths) so we don't
    # want to fail here.
    pass

import sys
import os
import stat


import ansible.playbook
import ansible.constants as C
import ansible.utils.template
from ansible import errors
from ansible import callbacks
from ansible import utils
from ansible.color import ANSIBLE_COLOR, stringc
from ansible.callbacks import display

def colorize(lead, num, color):
    """ Print 'lead' = 'num' in 'color' """
    if num != 0 and ANSIBLE_COLOR and color is not None:
        return "%s%s%-15s" % (stringc(lead, color), stringc("=", color), stringc(str(num), color))
    else:
        return "%s=%-4s" % (lead, str(num))

def hostcolor(host, stats, color=True):
    if ANSIBLE_COLOR and color:
        if stats['failures'] != 0 or stats['unreachable'] != 0:
            return "%-37s" % stringc(host, 'red')
        elif stats['changed'] != 0:
            return "%-37s" % stringc(host, 'yellow')
        else:
            return "%-37s" % stringc(host, 'green')
    return "%-26s" % host


def main(args):
    ''' run ansible-playbook operations '''

    # create parser for CLI options
    parser = utils.base_parser(
        constants=C,
        usage = "%prog playbook.yml",
        connect_opts=True,
        runas_opts=True,
        subset_opts=True,
        check_opts=True,
        diff_opts=True
    )
    parser.add_option('--vault-password', dest="vault_password",
       help="password for vault encrypted files")
    parser.add_option('--syntax-check', dest='syntax', action='store_true',
        help="perform a syntax check on the playbook, but do not execute it")
    parser.add_option('--list-tasks', dest='listtasks', action='store_true',
        help="list all tasks that would be executed")
    parser.add_option('--list-tags', dest='listtags', action='store_true',
        help="list all available tags")
    parser.add_option('--start-at-task', dest='start_at',
        help="start the playbook at the task matching this name")
    parser.add_option('--force-handlers', dest='force_handlers',
        default=C.DEFAULT_FORCE_HANDLERS, action='store_true',
        help="run handlers even if a task fails")
    parser.add_option('--flush-cache', dest='flush_cache', action='store_true',
        help="clear the fact cache")

    options, args = parser.parse_args(args)

    if len(args) == 0:
        parser.print_help(file=sys.stderr)
        return 1

    # privlege escalation command line arguments need to be mutually exclusive
    # utils.check_mutually_exclusive_privilege(options, parser)

    # if (options.ask_vault_pass and options.vault_password_file):
            # parser.error("--ask-vault-pass and --vault-password-file are mutually exclusive")

    sshpass = None
    becomepass = None
    vault_pass = None

    # options.ask_vault_pass = options.ask_vault_pass or C.DEFAULT_ASK_VAULT_PASS

    # if options.listhosts or options.syntax or options.listtasks or options.listtags:
    #     (_, _, vault_pass) = utils.ask_passwords(ask_vault_pass=options.ask_vault_pass)
    # else:
    #     options.ask_pass = options.ask_pass or C.DEFAULT_ASK_PASS
    #     # Never ask for an SSH password when we run with local connection
    #     if options.connection == "local":
    #         options.ask_pass = False

    #     # set pe options
    #     utils.normalize_become_options(options)
    #     prompt_method = utils.choose_pass_prompt(options)
    #     (sshpass, becomepass, vault_pass) = utils.ask_passwords(ask_pass=options.ask_pass,
    #                                                 become_ask_pass=options.become_ask_pass,
    #                                                 ask_vault_pass=options.ask_vault_pass,
    #                                                 become_method=prompt_method)

    # read vault_pass from a file
    # if not options.ask_vault_pass and options.vault_password_file:
        # vault_pass = utils.read_vault_file(options.vault_password_file)

    ## truiz: extra vars is dict with the vars and values
    #extra_vars = utils.parse_extra_vars(options.extra_vars, vault_pass)
    extra_vars = {'host': 'testing', 'vars_file': 'the_vars.yml'}
    print extra_vars

    ## truiz: this is just a list of playbooks
    playbooks = ['ansible/the_work.yml']
    for playbook in playbooks:
        print playbook
        if not os.path.exists(playbook):
            raise errors.AnsibleError("the playbook: %s could not be found" % playbook)
        if not (os.path.isfile(playbook) or stat.S_ISFIFO(os.stat(playbook).st_mode)):
            raise errors.AnsibleError("the playbook: %s does not appear to be a file" % playbook)

    ## truiz: is better to pass the inventory file
    inventory = ansible.inventory.Inventory('ansible/inventory', vault_password=vault_pass)
    print options.inventory
    print inventory
    # Note: slightly wrong, this is written so that implicit localhost
    # (which is not returned in list_hosts()) is taken into account for
    # warning if inventory is empty.  But it can't be taken into account for
    # checking if limit doesn't match any hosts.  Instead we don't worry about
    # limit if only implicit localhost was in inventory to start with.
    #
    # Fix this in v2
    no_hosts = False
    if len(inventory.list_hosts()) == 0:
        # Empty inventory
        utils.warning("provided hosts list is empty, only localhost is available")
        no_hosts = True
    #print options.subset
    #inventory.subset(options.subset)
    if len(inventory.list_hosts()) == 0 and no_hosts is False:
        # Invalid limit
        raise errors.AnsibleError("Specified --limit does not match any hosts")
    print options.become
    print options.become_method
    print options.become_user
    print options.remote_user
    print options.timeout
    print becomepass

    for playbook in playbooks:

        stats = callbacks.AggregateStats()
        playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
        print "start at %s " % str(options.start_at)
        if options.start_at:
            playbook_cb.start_at = options.start_at
        runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)
        print runner_cb

        pb = ansible.playbook.PlayBook(
            playbook=playbook,
            # module_path=options.module_path,
            inventory=inventory,
            # forks=options.forks,
            # remote_user=options.remote_user,
            # remote_pass=sshpass,
            callbacks=playbook_cb,
            runner_callbacks=runner_cb,
            stats=stats,
            timeout=options.timeout,
            # transport=options.connection,
            become=options.become,
            become_method=options.become_method,
            become_user=options.become_user,
            # become_pass=becomepass,
            extra_vars=extra_vars,
            private_key_file=options.private_key_file,
            # only_tags=only_tags,
            # skip_tags=skip_tags,
            check=options.check,
            diff=options.diff,
            # vault_password=vault_pass,
            force_handlers=options.force_handlers,
        )

        if options.flush_cache:
            display(callbacks.banner("FLUSHING FACT CACHE"))
            pb.SETUP_CACHE.flush()

        if options.listhosts or options.listtasks or options.syntax or options.listtags:
            print ''
            print 'playbook: %s' % playbook
            print ''
            playnum = 0
            for (play_ds, play_basedir) in zip(pb.playbook, pb.play_basedirs):
                playnum += 1
                play = ansible.playbook.Play(pb, play_ds, play_basedir,
                                              vault_password=pb.vault_password)
                label = play.name
                hosts = pb.inventory.list_hosts(play.hosts)

                if options.listhosts:
                    print '  play #%d (%s): host count=%d' % (playnum, label, len(hosts))
                    for host in hosts:
                        print '    %s' % host

                if options.listtags or options.listtasks:
                    print '  play #%d (%s):\tTAGS: [%s]' % (playnum, label,','.join(sorted(set(play.tags))))

                    if options.listtags:
                        tags = []
                        for task in pb.tasks_to_run_in_play(play):
                            tags.extend(task.tags)
                        print '    TASK TAGS: [%s]' % (', '.join(sorted(set(tags).difference(['untagged']))))

                    if options.listtasks:

                        for task in pb.tasks_to_run_in_play(play):
                            if getattr(task, 'name', None) is not None:
                                # meta tasks have no names
                                print '    %s\tTAGS: [%s]' % (task.name, ', '.join(sorted(set(task.tags).difference(['untagged']))))

                if options.listhosts or options.listtasks or options.listtags:
                    print ''
            continue

        if options.syntax:
            # if we've not exited by now then we are fine.
            print 'Playbook Syntax is fine'
            return 0

        failed_hosts = []
        unreachable_hosts = []

        try:
            print "Before run"
            res = pb.run()
            print "After run"
            ## truiz: returns a resume of all work done
            print res
            hosts = sorted(pb.stats.processed.keys())
            display(callbacks.banner("PLAY RECAP"))
            playbook_cb.on_stats(pb.stats)

            for h in hosts:
                t = pb.stats.summarize(h)
                if t['failures'] > 0:
                    failed_hosts.append(h)
                if t['unreachable'] > 0:
                    unreachable_hosts.append(h)

            retries = failed_hosts + unreachable_hosts

            if C.RETRY_FILES_ENABLED and len(retries) > 0:
                filename = pb.generate_retry_inventory(retries)
                if filename:
                    display("           to retry, use: --limit @%s\n" % filename)

            for h in hosts:
                t = pb.stats.summarize(h)

                display("%s : %s %s %s %s" % (
                    hostcolor(h, t),
                    colorize('ok', t['ok'], 'green'),
                    colorize('changed', t['changed'], 'yellow'),
                    colorize('unreachable', t['unreachable'], 'red'),
                    colorize('failed', t['failures'], 'red')),
                    screen_only=True
                )

                display("%s : %s %s %s %s" % (
                    hostcolor(h, t, False),
                    colorize('ok', t['ok'], None),
                    colorize('changed', t['changed'], None),
                    colorize('unreachable', t['unreachable'], None),
                    colorize('failed', t['failures'], None)),
                    log_only=True
                )


            print ""
            if len(failed_hosts) > 0:
                return 2
            if len(unreachable_hosts) > 0:
                return 3

        except errors.AnsibleError, e:
            display("ERROR: %s" % e, color='red')
            return 1

    return 0


if __name__ == "__main__":
    display(" ", log_only=True)
    display(" ".join(sys.argv), log_only=True)
    display(" ", log_only=True)
    try:
        sys.exit(main(sys.argv[1:]))
    except errors.AnsibleError, e:
        display("ERROR: %s" % e, color='red', stderr=True)
        sys.exit(1)
    except KeyboardInterrupt, ke:
        display("ERROR: interrupted", color='red', stderr=True)
        sys.exit(1)