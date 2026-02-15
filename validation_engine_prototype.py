#!/usr/bin/env python3
"""
NEP 2020 Timetable Validation & Formatting Engine
Final Output Processing System - Production Prototype

Author: NEP 2020 Development Team
Date: September 24, 2025
Version: 1.0.0

A comprehensive validation and formatting engine that validates solver output against
original data matrix, detects violations, and generates user-friendly timetable formats.

Industry-Level Architecture with Simplicity & Effectiveness Priority
"""

import os
import sys
import json
import csv
import logging
import traceback
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from enum import Enum
import re

# Simple dependency management - using only standard library + pandas
try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("ERROR: Required libraries not found. Please install: pip install pandas numpy")
    sys.exit(1)

# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

class ViolationSeverity(Enum):
    """Severity levels for validation violations"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ViolationType(Enum):
    """Types of validation violations"""
    # Hard constraint violations (critical)
    FACULTY_DOUBLE_BOOKING = "FACULTY_DOUBLE_BOOKING"
    ROOM_DOUBLE_BOOKING = "ROOM_DOUBLE_BOOKING"
    BATCH_TIME_CONFLICT = "BATCH_TIME_CONFLICT"
    EQUIPMENT_UNAVAILABLE = "EQUIPMENT_UNAVAILABLE"
    ROOM_CAPACITY_EXCEEDED = "ROOM_CAPACITY_EXCEEDED"
    FACULTY_COMPETENCY_MISMATCH = "FACULTY_COMPETENCY_MISMATCH"

    # Data integrity violations (critical)
    MISSING_COURSE_ASSIGNMENT = "MISSING_COURSE_ASSIGNMENT"
    INVALID_FACULTY_REFERENCE = "INVALID_FACULTY_REFERENCE"
    INVALID_ROOM_REFERENCE = "INVALID_ROOM_REFERENCE"
    INVALID_TIME_SLOT_REFERENCE = "INVALID_TIME_SLOT_REFERENCE"
    MISSING_BATCH_ASSIGNMENT = "MISSING_BATCH_ASSIGNMENT"

    # Soft constraint violations (warnings)
    FACULTY_PREFERENCE_VIOLATED = "FACULTY_PREFERENCE_VIOLATED"
    SUBOPTIMAL_ROOM_ASSIGNMENT = "SUBOPTIMAL_ROOM_ASSIGNMENT"
    NON_PREFERRED_TIME_SLOT = "NON_PREFERRED_TIME_SLOT"
    UNBALANCED_WORKLOAD = "UNBALANCED_WORKLOAD"
    LEARNING_OUTCOME_SUBOPTIMAL = "LEARNING_OUTCOME_SUBOPTIMAL"
    DUPLICATE_ASSIGNMENT = "DUPLICATE_ASSIGNMENT"

@dataclass
class ValidationViolation:
    """Individual validation violation record"""
    violation_type: ViolationType
    severity: ViolationSeverity
    entity_id: str
    entity_type: str  # COURSE, FACULTY, ROOM, BATCH, TIME_SLOT
    description: str
    technical_details: str
    suggested_fix: str
    weight: float
    is_critical: bool
    data_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ValidationResult:
    """Comprehensive validation results"""
    overall_status: str  # PASS, FAIL, WARNING
    total_violations: int
    critical_violations: int
    warning_violations: int
    violation_details: List[ValidationViolation]
    threshold_analysis: Dict[str, float]
    quality_metrics: Dict[str, Any]
    processing_time: float
    validation_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class TimetableCell:
    """Individual cell in the timetable matrix"""
    course_code: str
    course_name: str
    faculty_name: str
    batch_name: str
    student_count: int
    room_name: str
    equipment_required: List[str] = field(default_factory=list)
    session_type: str = "THEORY"
    violation_level: str = "NONE"  # NONE, WARNING, ERROR, CRITICAL

@dataclass
class TimetableMatrix:
    """Final timetable matrix structure"""
    matrix_data: Dict[str, Dict[str, TimetableCell]]  # [room_id][time_slot_id] -> TimetableCell
    days: List[str]
    time_slots: List[Dict[str, str]]
    rooms: List[Dict[str, str]]
    generation_timestamp: datetime
    validation_status: str
    total_sessions: int
    utilization_metrics: Dict[str, float]

# ============================================================================
# VALIDATION ENGINE - CRITICAL & ROBUST
# ============================================================================

class ValidationEngine:
    """Main validation engine for timetable solutions"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.setup_logging()

        # Violation type definitions with weights and criticality
        self.violation_definitions = {
            ViolationType.FACULTY_DOUBLE_BOOKING: {'weight': 10.0, 'critical': True},
            ViolationType.ROOM_DOUBLE_BOOKING: {'weight': 10.0, 'critical': True},
            ViolationType.BATCH_TIME_CONFLICT: {'weight': 10.0, 'critical': True},
            ViolationType.EQUIPMENT_UNAVAILABLE: {'weight': 8.0, 'critical': True},
            ViolationType.ROOM_CAPACITY_EXCEEDED: {'weight': 9.0, 'critical': True},
            ViolationType.FACULTY_COMPETENCY_MISMATCH: {'weight': 7.0, 'critical': True},
            ViolationType.MISSING_COURSE_ASSIGNMENT: {'weight': 8.0, 'critical': True},
            ViolationType.INVALID_FACULTY_REFERENCE: {'weight': 9.0, 'critical': True},
            ViolationType.INVALID_ROOM_REFERENCE: {'weight': 9.0, 'critical': True},
            ViolationType.INVALID_TIME_SLOT_REFERENCE: {'weight': 8.0, 'critical': True},
            ViolationType.MISSING_BATCH_ASSIGNMENT: {'weight': 7.0, 'critical': True},
            ViolationType.FACULTY_PREFERENCE_VIOLATED: {'weight': 3.0, 'critical': False},
            ViolationType.SUBOPTIMAL_ROOM_ASSIGNMENT: {'weight': 2.0, 'critical': False},
            ViolationType.NON_PREFERRED_TIME_SLOT: {'weight': 2.5, 'critical': False},
            ViolationType.UNBALANCED_WORKLOAD: {'weight': 4.0, 'critical': False},
            ViolationType.LEARNING_OUTCOME_SUBOPTIMAL: {'weight': 3.5, 'critical': False},
            ViolationType.DUPLICATE_ASSIGNMENT: {'weight': 6.0, 'critical': False}
        }

        # Critical thresholds for pass/fail decisions
        self.thresholds = {
            'CRITICAL_VIOLATION_RATIO': 0.05,        # Max 5% critical violations
            'TOTAL_VIOLATION_RATIO': 0.15,           # Max 15% total violations  
            'WEIGHTED_SCORE_THRESHOLD': 25.0,        # Max weighted violation score
            'FEASIBILITY_THRESHOLD': 0.95,           # Min 95% feasibility
            'QUALITY_SCORE_THRESHOLD': 7.0           # Min quality score (1-10)
        }

        # Output directories
        self.audit_dir = self.config.get('audit_directory', 'validation_audit_logs')
        self.error_dir = self.config.get('error_directory', 'validation_error_reports')
        self.output_dir = self.config.get('output_directory', 'validation_output')

        # Create directories
        for directory in [self.audit_dir, self.error_dir, self.output_dir]:
            os.makedirs(directory, exist_ok=True)

    def setup_logging(self):
        """Setup comprehensive audit logging"""
        audit_file = os.path.join(
            self.config.get('audit_directory', 'validation_audit_logs'),
            f'validation_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )

        os.makedirs(os.path.dirname(audit_file), exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            handlers=[
                logging.FileHandler(audit_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

        self.audit_logger = logging.getLogger('validation_engine')

    def validate_and_format(self, solver_output_file: str, data_matrix_file: str) -> Dict[str, Any]:
        """Main entry point for validation and formatting"""

        self.audit_logger.info("="*80)
        self.audit_logger.info("NEP 2020 TIMETABLE VALIDATION & FORMATTING ENGINE STARTED")
        self.audit_logger.info(f"Solver output: {solver_output_file}")
        self.audit_logger.info(f"Data matrix: {data_matrix_file}")
        self.audit_logger.info(f"Start time: {datetime.now()}")
        self.audit_logger.info("="*80)

        start_time = datetime.now()

        try:
            # Stage 1: Load input data
            solver_output = self._load_solver_output(solver_output_file)
            data_matrix = self._load_data_matrix(data_matrix_file)

            if not solver_output or not data_matrix:
                return self._generate_error_result("Failed to load input data")

            # Stage 2: Comprehensive validation
            self.audit_logger.info("STAGE 1: COMPREHENSIVE VALIDATION")
            validation_result = self._validate_solution(solver_output, data_matrix)
            self._log_validation_results(validation_result)

            # Stage 3: Threshold analysis and pass/fail decision
            self.audit_logger.info("STAGE 2: THRESHOLD ANALYSIS")
            threshold_result = self._analyze_thresholds(validation_result)
            self._log_threshold_analysis(threshold_result)

            # Stage 4: Generate formatted timetable matrix
            self.audit_logger.info("STAGE 3: MATRIX FORMATTING")
            timetable_matrix = self._format_timetable_matrix(solver_output, data_matrix, validation_result)
            self._log_matrix_generation(timetable_matrix)

            # Stage 5: Generate output files
            self.audit_logger.info("STAGE 4: OUTPUT GENERATION")
            output_files = self._generate_output_files(timetable_matrix, validation_result, threshold_result)

            # Final result compilation
            total_time = (datetime.now() - start_time).total_seconds()

            final_result = {
                'status': 'SUCCESS' if threshold_result['overall_pass'] else 'VALIDATION_FAILED',
                'validation_summary': {
                    'overall_status': validation_result.overall_status,
                    'total_violations': validation_result.total_violations,
                    'critical_violations': validation_result.critical_violations,
                    'warning_violations': validation_result.warning_violations,
                    'quality_score': validation_result.quality_metrics.get('quality_score', 0)
                },
                'threshold_analysis': threshold_result,
                'timetable_matrix': {
                    'total_sessions': timetable_matrix.total_sessions,
                    'validation_status': timetable_matrix.validation_status,
                    'utilization_metrics': timetable_matrix.utilization_metrics,
                    'generation_timestamp': timetable_matrix.generation_timestamp.isoformat()
                },
                'processing_summary': {
                    'total_processing_time': total_time,
                    'completion_timestamp': datetime.now().isoformat(),
                    'output_files': output_files
                }
            }

            self.audit_logger.info("="*80)
            self.audit_logger.info("VALIDATION & FORMATTING COMPLETED SUCCESSFULLY")
            self.audit_logger.info(f"Overall status: {validation_result.overall_status}")
            self.audit_logger.info(f"Critical violations: {validation_result.critical_violations}")
            self.audit_logger.info(f"Total sessions: {timetable_matrix.total_sessions}")
            self.audit_logger.info(f"Processing time: {total_time:.2f} seconds")
            self.audit_logger.info("="*80)

            return final_result

        except Exception as e:
            self.audit_logger.error(f"CRITICAL VALIDATION ENGINE FAILURE: {str(e)}")
            self.audit_logger.error(f"Stack trace: {traceback.format_exc()}")
            return self._generate_error_result(f"Critical failure: {str(e)}")

    def _load_solver_output(self, file_path: str) -> Optional[List[Dict]]:
        """Load solver output file (CSV or JSON)"""

        try:
            if file_path.endswith('.csv'):
                # Load CSV timetable
                df = pd.read_csv(file_path)
                solver_output = df.to_dict('records')
            elif file_path.endswith('.json'):
                # Load JSON timetable
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'timetable_entries' in data:
                        solver_output = data['timetable_entries']
                    else:
                        solver_output = data
            else:
                self.audit_logger.error(f"Unsupported solver output format: {file_path}")
                return None

            self.audit_logger.info(f"Solver output loaded: {len(solver_output)} entries")
            return solver_output

        except Exception as e:
            self.audit_logger.error(f"Failed to load solver output: {str(e)}")
            return None

    def _load_data_matrix(self, file_path: str) -> Optional[Dict]:
        """Load original data matrix from CSV processing engine"""

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_matrix = json.load(f)

            self.audit_logger.info(f"Data matrix loaded successfully from {file_path}")
            return data_matrix

        except Exception as e:
            self.audit_logger.error(f"Failed to load data matrix: {str(e)}")
            return None

    def _validate_solution(self, solver_output: List[Dict], data_matrix: Dict) -> ValidationResult:
        """Comprehensive solution validation"""

        violations = []

        try:
            # Extract reference data
            courses = data_matrix.get('data', {}).get('courses', [])
            faculty = data_matrix.get('data', {}).get('faculty', [])
            rooms = data_matrix.get('data', {}).get('rooms', [])
            time_slots = data_matrix.get('data', {}).get('time_slots', [])
            batches = data_matrix.get('data', {}).get('batches', [])

            # Create lookup dictionaries for efficient validation
            course_lookup = {c.get('course_id'): c for c in courses}
            faculty_lookup = {f.get('faculty_id'): f for f in faculty}
            room_lookup = {r.get('room_id'): r for r in rooms}
            time_slot_lookup = {t.get('timeslot_id'): t for t in time_slots}
            batch_lookup = {b.get('batch_id'): b for b in batches}

            # Track assignments for conflict detection
            faculty_assignments = {}  # faculty_id -> [time_slot_id]
            room_assignments = {}     # room_id -> [time_slot_id]
            batch_assignments = {}    # batch_id -> [time_slot_id]

            # Validate each timetable entry
            for entry_idx, entry in enumerate(solver_output):
                entry_violations = self._validate_single_entry(
                    entry, entry_idx, course_lookup, faculty_lookup, 
                    room_lookup, time_slot_lookup, batch_lookup,
                    faculty_assignments, room_assignments, batch_assignments
                )
                violations.extend(entry_violations)

            # Additional system-wide validations
            system_violations = self._validate_system_constraints(
                solver_output, data_matrix, course_lookup, faculty_lookup
            )
            violations.extend(system_violations)

            # Calculate validation metrics
            critical_violations = [v for v in violations if v.is_critical]
            warning_violations = [v for v in violations if not v.is_critical]

            # Determine overall status
            if len(critical_violations) > 0:
                overall_status = "FAIL"
            elif len(warning_violations) > 0:
                overall_status = "WARNING"
            else:
                overall_status = "PASS"

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(violations, solver_output)

            return ValidationResult(
                overall_status=overall_status,
                total_violations=len(violations),
                critical_violations=len(critical_violations),
                warning_violations=len(warning_violations),
                violation_details=violations,
                threshold_analysis={},  # Will be filled in threshold analysis
                quality_metrics=quality_metrics,
                processing_time=0.0  # Will be calculated by caller
            )

        except Exception as e:
            self.audit_logger.error(f"Validation failed: {str(e)}")
            return ValidationResult(
                overall_status="ERROR",
                total_violations=0,
                critical_violations=0,
                warning_violations=0,
                violation_details=[],
                threshold_analysis={},
                quality_metrics={'error': str(e)},
                processing_time=0.0
            )

    def _validate_single_entry(self, entry: Dict, entry_idx: int,
                              course_lookup: Dict, faculty_lookup: Dict,
                              room_lookup: Dict, time_slot_lookup: Dict, batch_lookup: Dict,
                              faculty_assignments: Dict, room_assignments: Dict, 
                              batch_assignments: Dict) -> List[ValidationViolation]:
        """Validate individual timetable entry"""

        violations = []

        # Extract entry data
        course_id = entry.get('course_id', '')
        faculty_id = entry.get('faculty_id', '')
        room_id = entry.get('room_id', '')
        time_slot_id = entry.get('time_slot_id', '')
        batch_id = entry.get('batch_id', '')

        # 1. Data integrity validation
        if course_id and course_id not in course_lookup:
            violations.append(ValidationViolation(
                violation_type=ViolationType.INVALID_FACULTY_REFERENCE,
                severity=ViolationSeverity.CRITICAL,
                entity_id=course_id,
                entity_type="COURSE",
                description=f"Course {course_id} not found in original data",
                technical_details=f"Entry {entry_idx}: course_id '{course_id}' has no corresponding record",
                suggested_fix="Verify course exists in master data or remove invalid entry",
                weight=self.violation_definitions[ViolationType.INVALID_FACULTY_REFERENCE]['weight'],
                is_critical=True,
                data_context={'entry_index': entry_idx, 'entry': entry}
            ))

        if faculty_id and faculty_id not in faculty_lookup:
            violations.append(ValidationViolation(
                violation_type=ViolationType.INVALID_FACULTY_REFERENCE,
                severity=ViolationSeverity.CRITICAL,
                entity_id=faculty_id,
                entity_type="FACULTY",
                description=f"Faculty {faculty_id} not found in original data",
                technical_details=f"Entry {entry_idx}: faculty_id '{faculty_id}' has no corresponding record",
                suggested_fix="Verify faculty exists in master data or assign different faculty",
                weight=self.violation_definitions[ViolationType.INVALID_FACULTY_REFERENCE]['weight'],
                is_critical=True,
                data_context={'entry_index': entry_idx, 'entry': entry}
            ))

        if room_id and room_id not in room_lookup:
            violations.append(ValidationViolation(
                violation_type=ViolationType.INVALID_ROOM_REFERENCE,
                severity=ViolationSeverity.CRITICAL,
                entity_id=room_id,
                entity_type="ROOM",
                description=f"Room {room_id} not found in original data",
                technical_details=f"Entry {entry_idx}: room_id '{room_id}' has no corresponding record",
                suggested_fix="Verify room exists in master data or assign different room",
                weight=self.violation_definitions[ViolationType.INVALID_ROOM_REFERENCE]['weight'],
                is_critical=True,
                data_context={'entry_index': entry_idx, 'entry': entry}
            ))

        if time_slot_id and time_slot_id not in time_slot_lookup:
            violations.append(ValidationViolation(
                violation_type=ViolationType.INVALID_TIME_SLOT_REFERENCE,
                severity=ViolationSeverity.CRITICAL,
                entity_id=time_slot_id,
                entity_type="TIME_SLOT",
                description=f"Time slot {time_slot_id} not found in original data",
                technical_details=f"Entry {entry_idx}: time_slot_id '{time_slot_id}' has no corresponding record",
                suggested_fix="Verify time slot exists in master data or assign different time slot",
                weight=self.violation_definitions[ViolationType.INVALID_TIME_SLOT_REFERENCE]['weight'],
                is_critical=True,
                data_context={'entry_index': entry_idx, 'entry': entry}
            ))

        if batch_id and batch_id not in batch_lookup:
            violations.append(ValidationViolation(
                violation_type=ViolationType.MISSING_BATCH_ASSIGNMENT,
                severity=ViolationSeverity.CRITICAL,
                entity_id=batch_id,
                entity_type="BATCH",
                description=f"Batch {batch_id} not found in original data",
                technical_details=f"Entry {entry_idx}: batch_id '{batch_id}' has no corresponding record",
                suggested_fix="Verify batch exists in master data or assign different batch",
                weight=self.violation_definitions[ViolationType.MISSING_BATCH_ASSIGNMENT]['weight'],
                is_critical=True,
                data_context={'entry_index': entry_idx, 'entry': entry}
            ))

        # 2. Conflict detection (only if all references are valid)
        if all([faculty_id in faculty_lookup, room_id in room_lookup, 
                time_slot_id in time_slot_lookup, batch_id in batch_lookup]):

            # Faculty double booking
            if faculty_id in faculty_assignments:
                if time_slot_id in faculty_assignments[faculty_id]:
                    violations.append(ValidationViolation(
                        violation_type=ViolationType.FACULTY_DOUBLE_BOOKING,
                        severity=ViolationSeverity.CRITICAL,
                        entity_id=faculty_id,
                        entity_type="FACULTY",
                        description=f"Faculty {faculty_lookup[faculty_id].get('faculty_name', faculty_id)} double booked at {time_slot_id}",
                        technical_details=f"Faculty {faculty_id} assigned to multiple sessions at {time_slot_id}",
                        suggested_fix="Reschedule one of the conflicting sessions to different time slot",
                        weight=self.violation_definitions[ViolationType.FACULTY_DOUBLE_BOOKING]['weight'],
                        is_critical=True,
                        data_context={'conflicting_time_slot': time_slot_id, 'faculty': faculty_lookup[faculty_id]}
                    ))
                else:
                    faculty_assignments[faculty_id].append(time_slot_id)
            else:
                faculty_assignments[faculty_id] = [time_slot_id]

            # Room double booking
            if room_id in room_assignments:
                if time_slot_id in room_assignments[room_id]:
                    violations.append(ValidationViolation(
                        violation_type=ViolationType.ROOM_DOUBLE_BOOKING,
                        severity=ViolationSeverity.CRITICAL,
                        entity_id=room_id,
                        entity_type="ROOM",
                        description=f"Room {room_lookup[room_id].get('room_name', room_id)} double booked at {time_slot_id}",
                        technical_details=f"Room {room_id} assigned to multiple sessions at {time_slot_id}",
                        suggested_fix="Reschedule one of the conflicting sessions to different room",
                        weight=self.violation_definitions[ViolationType.ROOM_DOUBLE_BOOKING]['weight'],
                        is_critical=True,
                        data_context={'conflicting_time_slot': time_slot_id, 'room': room_lookup[room_id]}
                    ))
                else:
                    room_assignments[room_id].append(time_slot_id)
            else:
                room_assignments[room_id] = [time_slot_id]

            # Batch time conflict
            if batch_id in batch_assignments:
                if time_slot_id in batch_assignments[batch_id]:
                    violations.append(ValidationViolation(
                        violation_type=ViolationType.BATCH_TIME_CONFLICT,
                        severity=ViolationSeverity.CRITICAL,
                        entity_id=batch_id,
                        entity_type="BATCH",
                        description=f"Batch {batch_lookup[batch_id].get('batch_name', batch_id)} has conflicting sessions at {time_slot_id}",
                        technical_details=f"Batch {batch_id} assigned to multiple sessions at {time_slot_id}",
                        suggested_fix="Reschedule one of the conflicting sessions to different time slot",
                        weight=self.violation_definitions[ViolationType.BATCH_TIME_CONFLICT]['weight'],
                        is_critical=True,
                        data_context={'conflicting_time_slot': time_slot_id, 'batch': batch_lookup[batch_id]}
                    ))
                else:
                    batch_assignments[batch_id].append(time_slot_id)
            else:
                batch_assignments[batch_id] = [time_slot_id]

            # 3. Capacity validation
            if room_id in room_lookup and batch_id in batch_lookup:
                room_capacity = room_lookup[room_id].get('capacity', 0)
                batch_size = batch_lookup[batch_id].get('student_count', 0)

                if batch_size > room_capacity:
                    violations.append(ValidationViolation(
                        violation_type=ViolationType.ROOM_CAPACITY_EXCEEDED,
                        severity=ViolationSeverity.CRITICAL,
                        entity_id=room_id,
                        entity_type="ROOM",
                        description=f"Room capacity ({room_capacity}) exceeded by batch size ({batch_size})",
                        technical_details=f"Room {room_id} capacity {room_capacity} < batch {batch_id} size {batch_size}",
                        suggested_fix="Assign larger room or split batch into smaller groups",
                        weight=self.violation_definitions[ViolationType.ROOM_CAPACITY_EXCEEDED]['weight'],
                        is_critical=True,
                        data_context={'room_capacity': room_capacity, 'batch_size': batch_size}
                    ))

        return violations

    def _validate_system_constraints(self, solver_output: List[Dict], data_matrix: Dict,
                                   course_lookup: Dict, faculty_lookup: Dict) -> List[ValidationViolation]:
        """Validate system-wide constraints"""

        violations = []

        # Check for missing course assignments
        scheduled_courses = set(entry.get('course_id') for entry in solver_output if entry.get('course_id'))
        all_courses = set(course_lookup.keys())
        missing_courses = all_courses - scheduled_courses

        for missing_course in missing_courses:
            violations.append(ValidationViolation(
                violation_type=ViolationType.MISSING_COURSE_ASSIGNMENT,
                severity=ViolationSeverity.CRITICAL,
                entity_id=missing_course,
                entity_type="COURSE",
                description=f"Course {course_lookup[missing_course].get('course_name', missing_course)} not scheduled",
                technical_details=f"Course {missing_course} appears in master data but has no timetable entries",
                suggested_fix="Add timetable entry for this course or mark as not requiring scheduling",
                weight=self.violation_definitions[ViolationType.MISSING_COURSE_ASSIGNMENT]['weight'],
                is_critical=True,
                data_context={'course_details': course_lookup[missing_course]}
            ))

        return violations

    def _calculate_quality_metrics(self, violations: List[ValidationViolation], 
                                 solver_output: List[Dict]) -> Dict[str, Any]:
        """Calculate solution quality metrics"""

        total_entries = len(solver_output)

        if total_entries == 0:
            return {'quality_score': 0, 'feasibility_score': 0}

        # Calculate weighted violation score
        total_weighted_score = sum(v.weight for v in violations)
        critical_violations = sum(1 for v in violations if v.is_critical)

        # Quality score (1-10 scale, higher is better)
        if total_weighted_score == 0:
            quality_score = 10.0
        else:
            # Normalize based on number of entries and average weight
            avg_violation_weight = total_weighted_score / len(violations) if violations else 0
            quality_score = max(1.0, 10.0 - (avg_violation_weight / total_entries) * 10)

        # Feasibility score (percentage of non-critical assignments)
        feasibility_score = max(0.0, 1.0 - (critical_violations / total_entries))

        return {
            'quality_score': round(quality_score, 2),
            'feasibility_score': round(feasibility_score, 3),
            'violation_density': round(len(violations) / total_entries, 3),
            'critical_violation_ratio': round(critical_violations / total_entries, 3),
            'average_violation_weight': round(total_weighted_score / len(violations), 2) if violations else 0
        }

    def _analyze_thresholds(self, validation_result: ValidationResult) -> Dict[str, Any]:
        """Analyze validation results against predefined thresholds"""

        try:
            total_violations = validation_result.total_violations
            critical_violations = validation_result.critical_violations

            # Calculate ratios (avoid division by zero)
            # Assuming we have total possible assignments (could be extracted from solver output)
            total_assignments = 100  # Placeholder - should be calculated from actual data

            critical_ratio = critical_violations / total_assignments if total_assignments > 0 else 0
            total_ratio = total_violations / total_assignments if total_assignments > 0 else 0

            # Weighted score calculation
            weighted_score = sum(v.weight for v in validation_result.violation_details)

            # Quality and feasibility scores
            quality_score = validation_result.quality_metrics.get('quality_score', 0)
            feasibility_score = validation_result.quality_metrics.get('feasibility_score', 0)

            # Threshold checks
            threshold_results = {
                'critical_ratio': critical_ratio,
                'critical_ratio_pass': critical_ratio <= self.thresholds['CRITICAL_VIOLATION_RATIO'],
                'total_ratio': total_ratio,
                'total_ratio_pass': total_ratio <= self.thresholds['TOTAL_VIOLATION_RATIO'],
                'weighted_score': weighted_score,
                'weighted_score_pass': weighted_score <= self.thresholds['WEIGHTED_SCORE_THRESHOLD'],
                'quality_score': quality_score,
                'quality_score_pass': quality_score >= self.thresholds['QUALITY_SCORE_THRESHOLD'],
                'feasibility_score': feasibility_score,
                'feasibility_score_pass': feasibility_score >= self.thresholds['FEASIBILITY_THRESHOLD']
            }

            # Overall pass/fail decision
            threshold_results['overall_pass'] = all([
                threshold_results['critical_ratio_pass'],
                threshold_results['total_ratio_pass'], 
                threshold_results['weighted_score_pass'],
                threshold_results['quality_score_pass'],
                threshold_results['feasibility_score_pass']
            ])

            return threshold_results

        except Exception as e:
            self.audit_logger.error(f"Threshold analysis failed: {str(e)}")
            return {'overall_pass': False, 'error': str(e)}

    def _format_timetable_matrix(self, solver_output: List[Dict], data_matrix: Dict, 
                               validation_result: ValidationResult) -> TimetableMatrix:
        """Format timetable into days vs time slots matrix"""

        try:
            # Extract reference data
            rooms = data_matrix.get('data', {}).get('rooms', [])
            time_slots = data_matrix.get('data', {}).get('time_slots', [])
            courses = data_matrix.get('data', {}).get('courses', [])
            faculty = data_matrix.get('data', {}).get('faculty', [])
            batches = data_matrix.get('data', {}).get('batches', [])

            # Create lookup dictionaries
            course_lookup = {c.get('course_id'): c for c in courses}
            faculty_lookup = {f.get('faculty_id'): f for f in faculty}
            room_lookup = {r.get('room_id'): r for r in rooms}
            batch_lookup = {b.get('batch_id'): b for b in batches}

            # Initialize matrix structure
            matrix_data = {}

            # Process each timetable entry
            for entry in solver_output:
                room_id = entry.get('room_id', '')
                time_slot_id = entry.get('time_slot_id', '')
                course_id = entry.get('course_id', '')
                faculty_id = entry.get('faculty_id', '')
                batch_id = entry.get('batch_id', '')

                if room_id and time_slot_id:
                    # Create room entry if not exists
                    if room_id not in matrix_data:
                        matrix_data[room_id] = {}

                    # Get entity details
                    course = course_lookup.get(course_id, {})
                    faculty = faculty_lookup.get(faculty_id, {})
                    batch = batch_lookup.get(batch_id, {})
                    room = room_lookup.get(room_id, {})

                    # Determine violation level for this entry
                    violation_level = self._get_entry_violation_level(
                        entry, validation_result.violation_details
                    )

                    # Create timetable cell
                    cell = TimetableCell(
                        course_code=course.get('course_code', 'UNKNOWN'),
                        course_name=course.get('course_name', 'Unknown Course'),
                        faculty_name=faculty.get('faculty_name', 'Unknown Faculty'),
                        batch_name=batch.get('batch_name', 'Unknown Batch'),
                        student_count=int(batch.get('student_count', 0)),
                        room_name=room.get('room_name', 'Unknown Room'),
                        equipment_required=course.get('equipment_required', []),
                        session_type=entry.get('session_type', 'THEORY'),
                        violation_level=violation_level
                    )

                    matrix_data[room_id][time_slot_id] = cell

            # Extract days for matrix organization
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

            # Calculate utilization metrics
            total_cells = len(rooms) * len(time_slots)
            occupied_cells = sum(len(room_slots) for room_slots in matrix_data.values())
            utilization = (occupied_cells / total_cells) * 100 if total_cells > 0 else 0

            utilization_metrics = {
                'overall_utilization': round(utilization, 2),
                'total_sessions': len(solver_output),
                'rooms_utilized': len(matrix_data),
                'time_slots_used': len(set(
                    slot_id for room_slots in matrix_data.values() 
                    for slot_id in room_slots.keys()
                ))
            }

            return TimetableMatrix(
                matrix_data=matrix_data,
                days=days,
                time_slots=time_slots,
                rooms=rooms,
                generation_timestamp=datetime.now(),
                validation_status=validation_result.overall_status,
                total_sessions=len(solver_output),
                utilization_metrics=utilization_metrics
            )

        except Exception as e:
            self.audit_logger.error(f"Matrix formatting failed: {str(e)}")
            return TimetableMatrix(
                matrix_data={},
                days=[],
                time_slots=[],
                rooms=[],
                generation_timestamp=datetime.now(),
                validation_status="ERROR",
                total_sessions=0,
                utilization_metrics={}
            )

    def _get_entry_violation_level(self, entry: Dict, violations: List[ValidationViolation]) -> str:
        """Determine violation level for a specific timetable entry"""

        entry_violations = []

        # Find violations related to this entry
        for violation in violations:
            if (violation.entity_id in [entry.get('course_id'), entry.get('faculty_id'), 
                                       entry.get('room_id'), entry.get('batch_id')] or
                violation.data_context.get('entry') == entry):
                entry_violations.append(violation)

        if not entry_violations:
            return "NONE"

        # Determine highest severity level
        if any(v.is_critical for v in entry_violations):
            return "CRITICAL"
        elif any(v.severity == ViolationSeverity.ERROR for v in entry_violations):
            return "ERROR"
        elif any(v.severity == ViolationSeverity.WARNING for v in entry_violations):
            return "WARNING"
        else:
            return "NONE"

    def _generate_output_files(self, timetable_matrix: TimetableMatrix, 
                             validation_result: ValidationResult,
                             threshold_result: Dict[str, Any]) -> List[str]:
        """Generate all output files"""

        output_files = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            # 1. Final timetable matrix CSV
            matrix_file = os.path.join(self.output_dir, f"final_timetable_matrix_{timestamp}.csv")
            self._generate_matrix_csv(timetable_matrix, matrix_file)
            output_files.append(matrix_file)

            # 2. Validation report
            validation_file = os.path.join(self.output_dir, f"validation_report_{timestamp}.txt")
            self._generate_validation_report(validation_result, threshold_result, validation_file)
            output_files.append(validation_file)

            # 3. Violation details CSV
            if validation_result.violation_details:
                violations_file = os.path.join(self.output_dir, f"violation_details_{timestamp}.csv")
                self._generate_violations_csv(validation_result.violation_details, violations_file)
                output_files.append(violations_file)

            # 4. Summary JSON
            summary_file = os.path.join(self.output_dir, f"validation_summary_{timestamp}.json")
            self._generate_summary_json(validation_result, threshold_result, timetable_matrix, summary_file)
            output_files.append(summary_file)

            self.audit_logger.info(f"Generated {len(output_files)} output files")
            return output_files

        except Exception as e:
            self.audit_logger.error(f"Output generation failed: {str(e)}")
            return []

    def _generate_matrix_csv(self, timetable_matrix: TimetableMatrix, file_path: str):
        """Generate final timetable matrix CSV in days vs time slots format"""

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header row: Room/Time, then all time slots
            time_slot_headers = []
            for time_slot in timetable_matrix.time_slots:
                day = time_slot.get('day_of_week', 'Unknown')
                start_time = time_slot.get('start_time', '00:00')
                end_time = time_slot.get('end_time', '00:00')
                header = f"{day} {start_time}-{end_time}"
                time_slot_headers.append(header)

            writer.writerow(['Room/Time Slot'] + time_slot_headers)

            # Data rows: One row per room
            for room in timetable_matrix.rooms:
                room_id = room.get('room_id', '')
                room_name = room.get('room_name', 'Unknown Room')

                row = [f"{room_name} ({room_id})"]

                # Fill each time slot column
                for time_slot in timetable_matrix.time_slots:
                    time_slot_id = time_slot.get('timeslot_id', '')

                    if (room_id in timetable_matrix.matrix_data and 
                        time_slot_id in timetable_matrix.matrix_data[room_id]):

                        cell = timetable_matrix.matrix_data[room_id][time_slot_id]
                        cell_content = (f"{cell.course_code}\n"
                                      f"{cell.faculty_name}\n"
                                      f"{cell.batch_name}\n"
                                      f"{cell.student_count} students")

                        if cell.violation_level != "NONE":
                            cell_content += f"\n[{cell.violation_level}]"

                        row.append(cell_content)
                    else:
                        row.append("Empty")

                writer.writerow(row)

    def _generate_validation_report(self, validation_result: ValidationResult, 
                                  threshold_result: Dict[str, Any], file_path: str):
        """Generate human-readable validation report"""

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("NEP 2020 TIMETABLE VALIDATION REPORT\n")
            f.write("="*60 + "\n\n")

            f.write(f"Validation Date: {validation_result.validation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Overall Status: {validation_result.overall_status}\n")
            f.write(f"Threshold Analysis: {'PASS' if threshold_result.get('overall_pass', False) else 'FAIL'}\n\n")

            f.write("VIOLATION SUMMARY:\n")
            f.write("-" * 30 + "\n")
            f.write(f"Total Violations: {validation_result.total_violations}\n")
            f.write(f"Critical Violations: {validation_result.critical_violations}\n")
            f.write(f"Warning Violations: {validation_result.warning_violations}\n\n")

            f.write("QUALITY METRICS:\n")
            f.write("-" * 30 + "\n")
            for metric, value in validation_result.quality_metrics.items():
                f.write(f"{metric.replace('_', ' ').title()}: {value}\n")

            f.write("\nTHRESHOLD ANALYSIS:\n")
            f.write("-" * 30 + "\n")
            for threshold, value in threshold_result.items():
                if not threshold.endswith('_pass'):
                    pass_status = threshold_result.get(f"{threshold}_pass", False)
                    status_text = "PASS" if pass_status else "FAIL"
                    f.write(f"{threshold.replace('_', ' ').title()}: {value} [{status_text}]\n")

            if validation_result.critical_violations > 0:
                f.write("\nCRITICAL VIOLATIONS (Top 10):\n")
                f.write("-" * 40 + "\n")
                critical_violations = [v for v in validation_result.violation_details if v.is_critical][:10]
                for i, violation in enumerate(critical_violations, 1):
                    f.write(f"{i}. {violation.description}\n")
                    f.write(f"   Fix: {violation.suggested_fix}\n\n")

    def _generate_violations_csv(self, violations: List[ValidationViolation], file_path: str):
        """Generate detailed violations CSV"""

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'violation_type', 'severity', 'entity_id', 'entity_type',
                'description', 'suggested_fix', 'weight', 'is_critical', 'timestamp'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for violation in violations:
                writer.writerow({
                    'violation_type': violation.violation_type.value,
                    'severity': violation.severity.value,
                    'entity_id': violation.entity_id,
                    'entity_type': violation.entity_type,
                    'description': violation.description,
                    'suggested_fix': violation.suggested_fix,
                    'weight': violation.weight,
                    'is_critical': violation.is_critical,
                    'timestamp': violation.timestamp.isoformat()
                })

    def _generate_summary_json(self, validation_result: ValidationResult, 
                             threshold_result: Dict[str, Any],
                             timetable_matrix: TimetableMatrix, file_path: str):
        """Generate JSON summary"""

        summary = {
            'validation_summary': {
                'overall_status': validation_result.overall_status,
                'total_violations': validation_result.total_violations,
                'critical_violations': validation_result.critical_violations,
                'warning_violations': validation_result.warning_violations,
                'quality_metrics': validation_result.quality_metrics
            },
            'threshold_analysis': threshold_result,
            'timetable_matrix': {
                'total_sessions': timetable_matrix.total_sessions,
                'validation_status': timetable_matrix.validation_status,
                'utilization_metrics': timetable_matrix.utilization_metrics
            },
            'generation_metadata': {
                'timestamp': datetime.now().isoformat(),
                'engine_version': '1.0.0'
            }
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)

    def _log_validation_results(self, result: ValidationResult):
        """Log validation results"""
        self.audit_logger.info("VALIDATION RESULTS:")
        self.audit_logger.info(f"  Overall Status: {result.overall_status}")
        self.audit_logger.info(f"  Total Violations: {result.total_violations}")
        self.audit_logger.info(f"  Critical Violations: {result.critical_violations}")
        self.audit_logger.info(f"  Warning Violations: {result.warning_violations}")

        if result.quality_metrics:
            self.audit_logger.info("  Quality Metrics:")
            for metric, value in result.quality_metrics.items():
                self.audit_logger.info(f"    {metric}: {value}")

    def _log_threshold_analysis(self, result: Dict[str, Any]):
        """Log threshold analysis results"""
        self.audit_logger.info("THRESHOLD ANALYSIS:")
        self.audit_logger.info(f"  Overall Pass: {result.get('overall_pass', False)}")

        for key, value in result.items():
            if not key.endswith('_pass') and key != 'overall_pass':
                pass_status = result.get(f"{key}_pass", False)
                self.audit_logger.info(f"  {key}: {value} ({'PASS' if pass_status else 'FAIL'})")

    def _log_matrix_generation(self, matrix: TimetableMatrix):
        """Log matrix generation results"""
        self.audit_logger.info("MATRIX GENERATION:")
        self.audit_logger.info(f"  Total Sessions: {matrix.total_sessions}")
        self.audit_logger.info(f"  Validation Status: {matrix.validation_status}")
        self.audit_logger.info(f"  Rooms Utilized: {len(matrix.matrix_data)}")

        if matrix.utilization_metrics:
            self.audit_logger.info("  Utilization Metrics:")
            for metric, value in matrix.utilization_metrics.items():
                self.audit_logger.info(f"    {metric}: {value}")

    def _generate_error_result(self, error_message: str) -> Dict[str, Any]:
        """Generate error result structure"""
        return {
            'status': 'FAILED',
            'error_message': error_message,
            'failure_timestamp': datetime.now().isoformat(),
            'suggested_actions': [
                'Check input file formats and paths',
                'Verify solver output contains required fields',
                'Review audit logs for detailed error information',
                'Contact system administrator if problem persists'
            ]
        }


def main():
    """Main entry point for Validation & Formatting Engine"""

    print("="*80)
    print("NEP 2020 TIMETABLE VALIDATION & FORMATTING ENGINE")
    print("Final Output Processing System - Production Prototype")
    print("Version 1.0.0 - Industry-Level Architecture")
    print("="*80)

    # Configuration
    config = {
        'audit_directory': 'validation_audit_logs',
        'error_directory': 'validation_error_reports',
        'output_directory': 'validation_output'
    }

    # Initialize engine
    engine = ValidationEngine(config)

    # Check for input files
    if len(sys.argv) > 2:
        solver_output_file = sys.argv[1]
        data_matrix_file = sys.argv[2]
    else:
        # Default input files
        solver_output_file = "solver_output/timetable_20250924_113000.csv"
        data_matrix_file = "validation_output/optimization_matrix_20250924_113000.json"

        if not all(os.path.exists(f) for f in [solver_output_file, data_matrix_file]):
            print(f"\n❌ ERROR: Input files not found")
            print("Usage:")
            print(f"  python {sys.argv[0]} <solver_output.csv> <data_matrix.json>")
            print("\nExample:")
            print(f"  python {sys.argv[0]} solver_output/timetable.csv validation_output/matrix.json")
            return

    # Execute validation and formatting
    print(f"\n🔍 Validating: {solver_output_file}")
    print(f"🔍 Against matrix: {data_matrix_file}")
    result = engine.validate_and_format(solver_output_file, data_matrix_file)

    # Print summary
    print("\n" + "="*80)
    if result['status'] == 'SUCCESS':
        validation_summary = result['validation_summary']
        threshold_analysis = result['threshold_analysis']

        print("🎉 VALIDATION & FORMATTING COMPLETED!")
        print(f"✅ Validation Status: {validation_summary['overall_status']}")
        print(f"✅ Threshold Analysis: {'PASS' if threshold_analysis.get('overall_pass', False) else 'FAIL'}")
        print(f"✅ Total Violations: {validation_summary['total_violations']}")
        print(f"✅ Critical Violations: {validation_summary['critical_violations']}")
        print(f"✅ Quality Score: {validation_summary.get('quality_score', 'N/A')}")
        print(f"✅ Total Sessions: {result['timetable_matrix']['total_sessions']}")

        if 'output_files' in result['processing_summary']:
            print("\n📁 OUTPUT FILES GENERATED:")
            for file_path in result['processing_summary']['output_files']:
                print(f"  • {file_path}")

    elif result['status'] == 'VALIDATION_FAILED':
        validation_summary = result['validation_summary']
        threshold_analysis = result['threshold_analysis']

        print("⚠️ VALIDATION COMPLETED WITH FAILURES!")
        print(f"❌ Validation Status: {validation_summary['overall_status']}")
        print(f"❌ Threshold Analysis: FAIL")
        print(f"❌ Critical Violations: {validation_summary['critical_violations']}")
        print(f"❌ Total Violations: {validation_summary['total_violations']}")

        print("\n🔧 THRESHOLD FAILURES:")
        for key, value in threshold_analysis.items():
            if key.endswith('_pass') and not value and key != 'overall_pass':
                metric_name = key.replace('_pass', '').replace('_', ' ').title()
                print(f"  • {metric_name}")

    else:
        print("❌ VALIDATION & FORMATTING FAILED!")
        print(f"Error: {result.get('error_message', 'Unknown error')}")

        if 'suggested_actions' in result:
            print("\n📋 SUGGESTED ACTIONS:")
            for action in result['suggested_actions']:
                print(f"  • {action}")

    print("\n📊 PROCESSING SUMMARY:")
    if 'processing_summary' in result:
        print(f"  • Total Time: {result['processing_summary'].get('total_processing_time', 'N/A'):.2f} seconds")
        print(f"  • Completion: {result['processing_summary'].get('completion_timestamp', 'N/A')}")

    print(f"\n📋 Audit Logs: {config['audit_directory']}")
    print(f"🚨 Error Reports: {config['error_directory']}")
    print(f"📁 Output Files: {config['output_directory']}")
    print("="*80)

    return result

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result['status'] in ['SUCCESS', 'VALIDATION_FAILED'] else 1)
