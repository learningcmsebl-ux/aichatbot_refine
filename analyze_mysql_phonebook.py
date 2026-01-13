"""
MySQL Phonebook Data Analysis Script
Connects to MySQL database, executes query, and performs comprehensive analysis
"""

import pymysql
import csv
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MySQLPhonebookAnalyzer:
    """Analyzer for MySQL phonebook data"""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        """
        Initialize MySQL connection
        
        Args:
            host: MySQL server host
            port: MySQL server port
            user: MySQL username
            password: MySQL password
            database: Database/schema name
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.data = []
        
    def connect(self, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """
        Establish MySQL connection with retry logic
        
        Args:
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay in seconds between retry attempts
        """
        for attempt in range(1, max_retries + 1):
            try:
                self.connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=10
                )
                logger.info(f"Successfully connected to MySQL at {self.host}:{self.port}/{self.database}")
                return True
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to MySQL after {max_retries} attempts: {e}")
        return False
    
    def disconnect(self):
        """Close MySQL connection"""
        if self.connection:
            self.connection.close()
            logger.info("MySQL connection closed")
    
    def execute_query(self, max_retries: int = 3, retry_delay: int = 2) -> List[Dict]:
        """
        Execute the phonebook query and return results with retry logic
        
        Args:
            max_retries: Maximum number of query retry attempts
            retry_delay: Delay in seconds between retry attempts
        
        Returns:
            List of employee records as dictionaries
        """
        query = """
        SELECT DISTINCT
            t2.meta_value AS Employee_Name,
            t1.post_title AS Employee_ID,
            t14.name AS Department,
            COALESCE(
                t_root.name,      -- Level 1 parent
                t_parent.name,    -- Level 2 parent
                t14.name          -- Level 3 (original category)
            ) AS Division,
            t3.meta_value AS Designation,
            t4.meta_value AS Email,
            TRIM(t7.meta_value) AS IP_EXT,
            t8.meta_value AS Mobile
        FROM ebl_posts t1
        LEFT JOIN ebl_postmeta t2 ON t1.ID = t2.post_id AND t2.meta_key = 'employee_name'
        LEFT JOIN ebl_postmeta t3 ON t1.ID = t3.post_id AND t3.meta_key = 'designation'
        LEFT JOIN ebl_postmeta t4 ON t1.ID = t4.post_id AND t4.meta_key = 'email_address'
        LEFT JOIN ebl_postmeta t7 ON t1.ID = t7.post_id AND t7.meta_key = 'ip'
        LEFT JOIN ebl_postmeta t8 ON t1.ID = t8.post_id AND t8.meta_key = 'mobile'
        LEFT JOIN ebl_term_relationships tr ON t1.ID = tr.object_id
        LEFT JOIN ebl_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
        LEFT JOIN ebl_terms t14 ON t14.term_id = tt.term_id
        LEFT JOIN ebl_term_taxonomy tt_parent ON tt.parent = tt_parent.term_taxonomy_id
        LEFT JOIN ebl_terms t_parent ON t_parent.term_id = tt_parent.term_id
        LEFT JOIN ebl_term_taxonomy tt_root ON tt_parent.parent = tt_root.term_taxonomy_id
        LEFT JOIN ebl_terms t_root ON t_root.term_id = tt_root.term_id
        WHERE t1.post_status = 'publish'
          AND t1.post_title <> ''
          AND t1.post_title NOT IN ('000.', '0000')
          AND TRIM(t7.meta_value) <> ''
          AND TRIM(t7.meta_value) <> '-'
          AND LENGTH(TRIM(t1.post_title)) > 1
          AND LENGTH(t1.post_title) = 4
          AND t14.name NOT LIKE '%Uncategorized%'
        """
        
        for attempt in range(1, max_retries + 1):
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    
                    # Convert to list of dicts and normalize field names
                    self.data = []
                    for row in results:
                        normalized = {
                            'full_name': row.get('Employee_Name', '').strip() if row.get('Employee_Name') else '',
                            'employee_id': row.get('Employee_ID', '').strip() if row.get('Employee_ID') else '',
                            'department': row.get('Department', '').strip() if row.get('Department') else '',
                            'division': row.get('Division', '').strip() if row.get('Division') else '',
                            'designation': row.get('Designation', '').strip() if row.get('Designation') else '',
                            'email': row.get('Email', '').strip() if row.get('Email') else '',
                            'ip_phone': row.get('IP_EXT', '').strip() if row.get('IP_EXT') else '',
                            'mobile': row.get('Mobile', '').strip() if row.get('Mobile') else ''
                        }
                        self.data.append(normalized)
                    
                    logger.info(f"Retrieved {len(self.data)} employee records from MySQL")
                    return self.data
                    
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Query execution attempt {attempt} failed: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    # Try to reconnect if connection was lost
                    try:
                        if self.connection:
                            self.connection.ping(reconnect=True)
                    except Exception:
                        logger.info("Connection lost. Attempting to reconnect...")
                        self.connect(max_retries=1, retry_delay=1)
                else:
                    logger.error(f"Error executing query after {max_retries} attempts: {e}")
        return []
    
    def analyze_statistics(self) -> Dict:
        """Calculate basic statistics"""
        stats = {
            'total_employees': len(self.data),
            'departments': {},
            'divisions': {},
            'designations': {},
            'with_email': 0,
            'without_email': 0,
            'with_mobile': 0,
            'without_mobile': 0,
            'with_ip_ext': 0,
            'without_ip_ext': 0
        }
        
        for emp in self.data:
            # Department distribution
            dept = emp.get('department', 'Unknown')
            stats['departments'][dept] = stats['departments'].get(dept, 0) + 1
            
            # Division distribution
            div = emp.get('division', 'Unknown')
            stats['divisions'][div] = stats['divisions'].get(div, 0) + 1
            
            # Designation distribution
            desig = emp.get('designation', 'Unknown')
            stats['designations'][desig] = stats['designations'].get(desig, 0) + 1
            
            # Email presence
            if emp.get('email'):
                stats['with_email'] += 1
            else:
                stats['without_email'] += 1
            
            # Mobile presence
            if emp.get('mobile'):
                stats['with_mobile'] += 1
            else:
                stats['without_mobile'] += 1
            
            # IP extension presence
            if emp.get('ip_phone'):
                stats['with_ip_ext'] += 1
            else:
                stats['without_ip_ext'] += 1
        
        return stats
    
    def analyze_data_quality(self) -> Dict:
        """Perform data quality checks"""
        quality = {
            'missing_name': 0,
            'missing_email': 0,
            'missing_mobile': 0,
            'missing_department': 0,
            'missing_division': 0,
            'missing_designation': 0,
            'duplicate_employee_ids': [],
            'invalid_emails': [],
            'invalid_mobiles': [],
            'empty_ip_extensions': 0
        }
        
        employee_ids = {}
        
        for idx, emp in enumerate(self.data):
            # Check missing fields
            if not emp.get('full_name'):
                quality['missing_name'] += 1
            if not emp.get('email'):
                quality['missing_email'] += 1
            if not emp.get('mobile'):
                quality['missing_mobile'] += 1
            if not emp.get('department'):
                quality['missing_department'] += 1
            if not emp.get('division'):
                quality['missing_division'] += 1
            if not emp.get('designation'):
                quality['missing_designation'] += 1
            
            # Check duplicate employee IDs
            emp_id = emp.get('employee_id')
            if emp_id:
                if emp_id in employee_ids:
                    quality['duplicate_employee_ids'].append({
                        'employee_id': emp_id,
                        'first_occurrence': employee_ids[emp_id],
                        'duplicate_occurrence': idx
                    })
                else:
                    employee_ids[emp_id] = idx
            
            # Validate email format
            email = emp.get('email', '')
            if email and not self._is_valid_email(email):
                quality['invalid_emails'].append({
                    'employee_id': emp.get('employee_id', 'Unknown'),
                    'name': emp.get('full_name', 'Unknown'),
                    'email': email
                })
            
            # Validate mobile format
            mobile = emp.get('mobile', '')
            if mobile and not self._is_valid_mobile(mobile):
                quality['invalid_mobiles'].append({
                    'employee_id': emp.get('employee_id', 'Unknown'),
                    'name': emp.get('full_name', 'Unknown'),
                    'mobile': mobile
                })
            
            # Check empty IP extensions
            ip_ext = emp.get('ip_phone', '').strip()
            if not ip_ext or ip_ext == '-':
                quality['empty_ip_extensions'] += 1
        
        return quality
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _is_valid_mobile(self, mobile: str) -> bool:
        """Validate mobile number format (basic check)"""
        # Remove spaces, dashes, and common prefixes
        cleaned = re.sub(r'[\s\-\(\)]', '', mobile)
        # Check if it's mostly digits and has reasonable length (10-15 digits)
        return cleaned.isdigit() and 10 <= len(cleaned) <= 15
    
    def analyze_insights(self) -> Dict:
        """Generate data insights"""
        insights = {
            'top_designations': [],
            'department_sizes': {},
            'division_hierarchy': {},
            'contact_completeness': {}
        }
        
        # Top designations
        designation_counts = Counter(emp.get('designation', 'Unknown') for emp in self.data if emp.get('designation'))
        insights['top_designations'] = designation_counts.most_common(20)
        
        # Department sizes
        dept_counts = Counter(emp.get('department', 'Unknown') for emp in self.data)
        insights['department_sizes'] = dict(dept_counts.most_common())
        
        # Division hierarchy (division -> departments)
        div_dept_map = defaultdict(set)
        for emp in self.data:
            div = emp.get('division', 'Unknown')
            dept = emp.get('department', 'Unknown')
            if div and dept:
                div_dept_map[div].add(dept)
        
        insights['division_hierarchy'] = {
            div: list(depts) for div, depts in div_dept_map.items()
        }
        
        # Contact completeness per department
        dept_completeness = defaultdict(lambda: {'total': 0, 'with_email': 0, 'with_mobile': 0, 'with_ip': 0})
        for emp in self.data:
            dept = emp.get('department', 'Unknown')
            dept_completeness[dept]['total'] += 1
            if emp.get('email'):
                dept_completeness[dept]['with_email'] += 1
            if emp.get('mobile'):
                dept_completeness[dept]['with_mobile'] += 1
            if emp.get('ip_phone'):
                dept_completeness[dept]['with_ip'] += 1
        
        # Calculate completeness percentages
        for dept, counts in dept_completeness.items():
            total = counts['total']
            insights['contact_completeness'][dept] = {
                'total': total,
                'email_completeness': round((counts['with_email'] / total * 100) if total > 0 else 0, 2),
                'mobile_completeness': round((counts['with_mobile'] / total * 100) if total > 0 else 0, 2),
                'ip_completeness': round((counts['with_ip'] / total * 100) if total > 0 else 0, 2),
                'overall_completeness': round(
                    ((counts['with_email'] + counts['with_mobile'] + counts['with_ip']) / (total * 3) * 100)
                    if total > 0 else 0, 2
                )
            }
        
        return insights
    
    def export_to_csv(self, filename: str = 'phonebook_export.csv'):
        """Export data to CSV file"""
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                if not self.data:
                    logger.warning("No data to export")
                    return
                
                fieldnames = ['full_name', 'employee_id', 'department', 'division', 
                            'designation', 'email', 'ip_phone', 'mobile']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for emp in self.data:
                    writer.writerow(emp)
            
            logger.info(f"Exported {len(self.data)} records to {filename}")
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
    
    def export_to_json(self, filename: str = 'phonebook_data.json'):
        """Export data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(self.data, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(self.data)} records to {filename}")
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
    
    def generate_report(self, filename: str = 'phonebook_analysis_report.txt'):
        """Generate comprehensive analysis report"""
        try:
            stats = self.analyze_statistics()
            quality = self.analyze_data_quality()
            insights = self.analyze_insights()
            
            with open(filename, 'w', encoding='utf-8') as report:
                report.write("=" * 80 + "\n")
                report.write("PHONEBOOK DATA ANALYSIS REPORT\n")
                report.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                report.write("=" * 80 + "\n\n")
                
                # Basic Statistics
                report.write("BASIC STATISTICS\n")
                report.write("-" * 80 + "\n")
                report.write(f"Total Employees: {stats['total_employees']}\n")
                report.write(f"With Email: {stats['with_email']} ({stats['with_email']/stats['total_employees']*100:.1f}%)\n")
                report.write(f"Without Email: {stats['without_email']} ({stats['without_email']/stats['total_employees']*100:.1f}%)\n")
                report.write(f"With Mobile: {stats['with_mobile']} ({stats['with_mobile']/stats['total_employees']*100:.1f}%)\n")
                report.write(f"Without Mobile: {stats['without_mobile']} ({stats['without_mobile']/stats['total_employees']*100:.1f}%)\n")
                report.write(f"With IP Extension: {stats['with_ip_ext']} ({stats['with_ip_ext']/stats['total_employees']*100:.1f}%)\n")
                report.write(f"Without IP Extension: {stats['without_ip_ext']} ({stats['without_ip_ext']/stats['total_employees']*100:.1f}%)\n\n")
                
                # Department Distribution
                report.write("DEPARTMENT DISTRIBUTION (Top 20)\n")
                report.write("-" * 80 + "\n")
                sorted_depts = sorted(stats['departments'].items(), key=lambda x: x[1], reverse=True)[:20]
                for dept, count in sorted_depts:
                    report.write(f"  {dept}: {count}\n")
                report.write("\n")
                
                # Division Distribution
                report.write("DIVISION DISTRIBUTION (Top 20)\n")
                report.write("-" * 80 + "\n")
                sorted_divs = sorted(stats['divisions'].items(), key=lambda x: x[1], reverse=True)[:20]
                for div, count in sorted_divs:
                    report.write(f"  {div}: {count}\n")
                report.write("\n")
                
                # Top Designations
                report.write("TOP DESIGNATIONS (Top 20)\n")
                report.write("-" * 80 + "\n")
                for desig, count in insights['top_designations'][:20]:
                    report.write(f"  {desig}: {count}\n")
                report.write("\n")
                
                # Data Quality
                report.write("DATA QUALITY CHECKS\n")
                report.write("-" * 80 + "\n")
                report.write(f"Missing Names: {quality['missing_name']}\n")
                report.write(f"Missing Emails: {quality['missing_email']}\n")
                report.write(f"Missing Mobile: {quality['missing_mobile']}\n")
                report.write(f"Missing Department: {quality['missing_department']}\n")
                report.write(f"Missing Division: {quality['missing_division']}\n")
                report.write(f"Missing Designation: {quality['missing_designation']}\n")
                report.write(f"Empty IP Extensions: {quality['empty_ip_extensions']}\n")
                report.write(f"Duplicate Employee IDs: {len(quality['duplicate_employee_ids'])}\n")
                report.write(f"Invalid Email Formats: {len(quality['invalid_emails'])}\n")
                report.write(f"Invalid Mobile Formats: {len(quality['invalid_mobiles'])}\n\n")
                
                # Duplicate Employee IDs
                if quality['duplicate_employee_ids']:
                    report.write("DUPLICATE EMPLOYEE IDs\n")
                    report.write("-" * 80 + "\n")
                    for dup in quality['duplicate_employee_ids'][:20]:
                        report.write(f"  Employee ID: {dup['employee_id']} (appears multiple times)\n")
                    report.write("\n")
                
                # Invalid Emails
                if quality['invalid_emails']:
                    report.write("INVALID EMAIL FORMATS (First 20)\n")
                    report.write("-" * 80 + "\n")
                    for invalid in quality['invalid_emails'][:20]:
                        report.write(f"  {invalid['name']} ({invalid['employee_id']}): {invalid['email']}\n")
                    report.write("\n")
                
                # Invalid Mobiles
                if quality['invalid_mobiles']:
                    report.write("INVALID MOBILE FORMATS (First 20)\n")
                    report.write("-" * 80 + "\n")
                    for invalid in quality['invalid_mobiles'][:20]:
                        report.write(f"  {invalid['name']} ({invalid['employee_id']}): {invalid['mobile']}\n")
                    report.write("\n")
                
                # Contact Completeness
                report.write("CONTACT COMPLETENESS BY DEPARTMENT\n")
                report.write("-" * 80 + "\n")
                sorted_completeness = sorted(
                    insights['contact_completeness'].items(),
                    key=lambda x: x[1]['overall_completeness'],
                    reverse=True
                )
                for dept, comp in sorted_completeness[:20]:
                    report.write(f"\n{dept}:\n")
                    report.write(f"  Total Employees: {comp['total']}\n")
                    report.write(f"  Email Completeness: {comp['email_completeness']}%\n")
                    report.write(f"  Mobile Completeness: {comp['mobile_completeness']}%\n")
                    report.write(f"  IP Extension Completeness: {comp['ip_completeness']}%\n")
                    report.write(f"  Overall Completeness: {comp['overall_completeness']}%\n")
                report.write("\n")
                
                # Division Hierarchy
                report.write("DIVISION HIERARCHY\n")
                report.write("-" * 80 + "\n")
                for div, depts in list(insights['division_hierarchy'].items())[:20]:
                    report.write(f"\n{div}:\n")
                    for dept in depts:
                        report.write(f"  - {dept}\n")
            
            logger.info(f"Analysis report saved to {filename}")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
    
    def display_summary(self):
        """Display summary statistics to console"""
        stats = self.analyze_statistics()
        quality = self.analyze_data_quality()
        
        print("\n" + "=" * 80)
        print("PHONEBOOK DATA ANALYSIS SUMMARY")
        print("=" * 80)
        print(f"\nTotal Employees: {stats['total_employees']}")
        print(f"\nContact Information:")
        print(f"  With Email: {stats['with_email']} ({stats['with_email']/stats['total_employees']*100:.1f}%)")
        print(f"  With Mobile: {stats['with_mobile']} ({stats['with_mobile']/stats['total_employees']*100:.1f}%)")
        print(f"  With IP Extension: {stats['with_ip_ext']} ({stats['with_ip_ext']/stats['total_employees']*100:.1f}%)")
        
        print(f"\nData Quality Issues:")
        print(f"  Missing Names: {quality['missing_name']}")
        print(f"  Missing Emails: {quality['missing_email']}")
        print(f"  Missing Mobile: {quality['missing_mobile']}")
        print(f"  Duplicate Employee IDs: {len(quality['duplicate_employee_ids'])}")
        print(f"  Invalid Email Formats: {len(quality['invalid_emails'])}")
        print(f"  Invalid Mobile Formats: {len(quality['invalid_mobiles'])}")
        
        print(f"\nTop 10 Departments:")
        sorted_depts = sorted(stats['departments'].items(), key=lambda x: x[1], reverse=True)[:10]
        for dept, count in sorted_depts:
            print(f"  {dept}: {count}")
        
        print("\n" + "=" * 80 + "\n")


def main():
    """Main execution function"""
    # MySQL connection parameters
    MYSQL_HOST = '192.168.3.57'
    MYSQL_PORT = 3306
    MYSQL_USER = 'tanvir'
    MYSQL_PASSWORD = 'tanvir'
    MYSQL_DATABASE = 'ebl_home'
    
    # Create analyzer instance
    analyzer = MySQLPhonebookAnalyzer(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    
    try:
        # Connect to MySQL
        if not analyzer.connect():
            logger.error("Failed to connect to MySQL. Exiting.")
            return
        
        # Execute query
        logger.info("Executing phonebook query...")
        data = analyzer.execute_query()
        
        if not data:
            logger.warning("No data retrieved from query")
            return
        
        # Display summary
        analyzer.display_summary()
        
        # Generate exports
        logger.info("Generating exports...")
        analyzer.export_to_csv('phonebook_export.csv')
        analyzer.export_to_json('phonebook_data.json')
        analyzer.generate_report('phonebook_analysis_report.txt')
        
        logger.info("Analysis complete!")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
    finally:
        analyzer.disconnect()


if __name__ == "__main__":
    main()

