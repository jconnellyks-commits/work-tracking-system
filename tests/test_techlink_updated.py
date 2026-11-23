"""
TechLink "Updated" email parsing. Run: python tests/test_techlink_updated.py

Bodies copy the wording and line wrapping of real emails, with made-up sites.
"""
import base64
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'email_parser'))

from parsers.techlink import classify_techlink_subject, parse_techlink_updated  # noqa: E402

BODY = """

Hello,

This is a courtesy notification that the status of Techlink Work Order
#500001
[https://portal.techlinksvc.net/admin/?mod=workorders&id=500001] has
{change}

SITE INFORMATION
 Example Gym: Example Gym
100 Main St
 Ste 180
 Wichita, KS 67205
 Pat
555 555-1018

WORK ORDER DETAILS
 Client PO: Repair
{schedule}
Summary: Repair

TechLink Services
"""

ON_SITE = 'changed from SCHEDULED to TECH ON SITE.'
OFF_SITE = 'changed from INCOMPLETE to TECH OFF SITE.'
RESCHEDULE = ('changed, installation start time has been updated from OCTOBER 5,\n'
              '2026, 3:00 PM to OCTOBER 1, 2026, 2:00 PM.')


def message(change, schedule, sent_utc):
    text = BODY.format(change=change, schedule=f'Scheduled Install Time: {schedule}' if schedule else '')
    return {
        'internalDate': str(int(datetime(*sent_utc, tzinfo=timezone.utc).timestamp() * 1000)),
        'payload': {'mimeType': 'multipart/alternative', 'parts': [{
            'mimeType': 'text/plain',
            'body': {'data': base64.urlsafe_b64encode(text.encode()).decode()},
        }]},
    }


def parse(*args):
    return parse_techlink_updated(message(*args), '500001')


class Subject(unittest.TestCase):
    def test_updated(self):
        self.assertEqual(classify_techlink_subject(
            'TechLink WO #500001 Updated: Example Gym: (Repair) Example Gym'), ('updated', '500001'))

    def test_others_unchanged(self):
        for subject, want in [
            ('TechLink Work Order #5 Assigned', ('assigned', '5')),
            ('TechLink Install Reminder: WO #5, Example', ('reminder', '5')),
            ('TechLink WO #5 - Note Added: Example: Updated: plan', (None, None)),
            ('TechLink Work Order 5 is Ready for Your Invoice', (None, None)),
            ('TechLink Work Order #5 Available for Tech someone', (None, None)),
        ]:
            self.assertEqual(classify_techlink_subject(subject), want, subject)


class OnSite(unittest.TestCase):
    def test_dates_and_starts_the_job(self):
        r = parse(ON_SITE, 'Nov 18, 2026 4:00 PM (CST)', (2026, 11, 18, 20, 56))
        self.assertEqual((r['job_date'], r['scheduled_start_time'], r['status']),
                         ('2026-11-18', '16:00', 'in_progress'))

    def test_stale_schedule_loses_to_the_day_it_was_sent(self):
        # TL-424393: on site Oct 1 while the body still said Oct 5
        r = parse(ON_SITE, 'Oct 5, 2026 3:00 PM (CDT)', (2026, 10, 1, 18, 54))
        self.assertEqual((r['job_date'], r['scheduled_start_time']), ('2026-10-01', None))

    def test_evening_is_the_local_day_not_the_utc_day(self):
        # TL-418421: 8:32 PM Central is already the next day in UTC
        r = parse(ON_SITE, 'Aug 3, 2026 9:00 PM (CDT)', (2026, 8, 4, 1, 32))
        self.assertEqual((r['job_date'], r['scheduled_start_time']), ('2026-08-03', '21:00'))

    def test_dated_without_a_schedule_line(self):
        r = parse(ON_SITE, None, (2026, 11, 18, 20, 56))
        self.assertEqual((r['job_date'], r['scheduled_start_time']), ('2026-11-18', None))

    def test_carries_enough_to_create_a_missing_job(self):
        r = parse(ON_SITE, 'Nov 18, 2026 4:00 PM (CST)', (2026, 11, 18, 20, 56))
        self.assertEqual(r['client_name'], 'Example Gym: Example Gym')
        self.assertEqual(r['address'], '100 Main St, Ste 180, Wichita, KS 67205')
        self.assertEqual(r['description'], 'Repair')
        self.assertTrue(r['external_url'].endswith('id=500001'))
        self.assertEqual(r['email_type'], 'updated')


class OffSite(unittest.TestCase):
    def test_never_completes_the_job(self):
        r = parse(OFF_SITE, 'Nov 18, 2026 4:00 PM (CST)', (2026, 11, 18, 22, 58))
        self.assertEqual(r['status'], 'in_progress')

    def test_uses_the_schedule_not_the_send_day(self):
        # Checkouts get filed late: the next morning, or days after
        r = parse(OFF_SITE, 'Jul 9, 2026 9:00 AM (CDT)', (2026, 7, 10, 23, 56))
        self.assertEqual((r['job_date'], r['scheduled_start_time']), ('2026-07-09', '09:00'))


class Reschedule(unittest.TestCase):
    def test_moves_the_date_and_leaves_status_alone(self):
        r = parse(RESCHEDULE, 'Oct 1, 2026 2:00 PM (CDT)', (2026, 9, 28, 18, 54))
        self.assertEqual((r['job_date'], r['scheduled_start_time'], r['status']),
                         ('2026-10-01', '14:00', None))


class Unrecognized(unittest.TestCase):
    """None sends the email to review rather than guessing."""

    def test_unknown_status(self):
        self.assertIsNone(parse('changed from SCHEDULED to CANCELED.', 'Nov 18, 2026 4:00 PM (CST)',
                                (2026, 11, 18, 20, 56)))

    def test_unknown_wording(self):
        self.assertIsNone(parse('been looked at.', 'Nov 18, 2026 4:00 PM (CST)', (2026, 11, 18, 20, 56)))

    def test_reschedule_with_unreadable_date(self):
        self.assertIsNone(parse(RESCHEDULE, 'TBD', (2026, 9, 28, 18, 54)))

    def test_empty_body(self):
        self.assertIsNone(parse_techlink_updated({'internalDate': '0', 'payload': {}}, '500001'))


if __name__ == '__main__':
    unittest.main()
