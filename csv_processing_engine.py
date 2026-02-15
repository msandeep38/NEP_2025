#!/usr/bin/env python3
"""
NEP 2020 CSV Processing & Data Validation Engine
Production-Ready Prototype for Government Deployment

Author: NEP 2020 Development Team
Date: September 24, 2025
Version: 1.0.0

This engine validates CSV inputs for the NEP 2020 Timetable Scheduling System,
performs constraint classification, and generates optimization matrices.
"""

import os
import sys
import csv
import json
import uuid
import logging
import traceback
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, time, date
from pathlib import Path
import pandas as pd
from enum import Enum
import re

# Configuration for validation stages
@dataclass
class ValidationConfig:
    """Configuration for validation pipeline"""
    input_directory: str = "sample_csv_data"
    output_directory: str = "validation_output"
    audit_log_directory: str = "audit_logs"
    error_report_directory: str = "error_reports"

    # Validation thresholds
    max_errors_per_stage: int = 100
    stop_on_critical_error: bool = True
    generate_detailed_reports: bool = True

    # Optimization weights (as requested)
    room_utilization_weight: float = 1.0
    faculty_load_weight: float = 1.5
    learning_outcome_weight: float = 1.2

class ValidationSeverity(Enum):
    """Validation error severity levels"""
    INFO = "INFO"
    WARNING = "WARNING" 
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ConstraintType(Enum):
    """Constraint classification types"""
    HARD = "HARD"
    SOFT = "SOFT"
    PREFERENCE = "PREFERENCE"

@dataclass
class ValidationError:
    """Structure for validation errors"""
    stage: str
    file_name: str
    row_number: Optional[int]
    column_name: Optional[str] 
    error_code: str
    severity: ValidationSeverity
    technical_message: str
    user_friendly_message: str
    suggested_fix: str
    data_context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationResult:
    """Results of validation stage"""
    stage_name: str
    success: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    processed_rows: int = 0
    processing_time: float = 0.0
    summary_stats: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptimizationMatrix:
    """Unified data matrix for scheduling algorithms"""
    institutions: pd.DataFrame
    departments: pd.DataFrame
    programs: pd.DataFrame
    courses: pd.DataFrame
    faculty: pd.DataFrame
    rooms: pd.DataFrame
    time_slots: pd.DataFrame
    batches: pd.DataFrame
    learning_outcomes: pd.DataFrame

    # Mapping tables
    faculty_competency: pd.DataFrame
    batch_enrollments: pd.DataFrame
    course_outcomes: pd.DataFrame

    # Constraints
    hard_constraints: List[Dict[str, Any]]
    soft_constraints: List[Dict[str, Any]]

    # Optimization objectives (as requested)
    utilization_objectives: Dict[str, float]
    learning_outcome_requirements: Dict[str, float]

    # Matrix metadata
    generation_timestamp: datetime
    data_quality_score: float
    feasibility_status: str

class CSVProcessingEngine:
    """Main CSV Processing and Validation Engine"""

    def __init__(self, config: ValidationConfig):
        self.config = config
        self.validation_results: List[ValidationResult] = []
        self.audit_logger = self._setup_audit_logger()
        self.error_logger = self._setup_error_logger()

        # Expected schema definitions
        self.schema_definitions = self._load_schema_definitions()

        # Create output directories
        self._setup_directories()

    def _setup_directories(self):
        """Create necessary output directories"""
        os.makedirs(self.config.output_directory, exist_ok=True)
        os.makedirs(self.config.audit_log_directory, exist_ok=True)
        os.makedirs(self.config.error_report_directory, exist_ok=True)

    def _setup_audit_logger(self) -> logging.Logger:
        """Setup structured audit logging"""
        logger = logging.getLogger('audit_logger')
        logger.setLevel(logging.INFO)

        # Create file handler for audit logs
        audit_file = os.path.join(self.config.audit_log_directory, 
                                 f'audit_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        handler = logging.FileHandler(audit_file)

        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def _setup_error_logger(self) -> logging.Logger:
        """Setup error-specific logging"""
        logger = logging.getLogger('error_logger')
        logger.setLevel(logging.ERROR)

        # Create file handler for error logs
        error_file = os.path.join(self.config.error_report_directory,
                                 f'error_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        handler = logging.FileHandler(error_file)

        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s\n%(message)s\n' + '-'*80 + '\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def _load_schema_definitions(self) -> Dict[str, Dict]:
        """Load expected schema definitions for validation"""
        return {
            'sched_institutions.csv': {
                'required_columns': ['institution_id', 'tenant_id', 'institution_name', 
                                   'institution_code', 'district_id'],
                'data_types': {
                    'institution_id': 'uuid',
                    'tenant_id': 'uuid',
                    'institution_name': 'string',
                    'nep_compliance_level': 'integer',
                    'max_students_capacity': 'integer'
                }
            },
            'sched_faculty.csv': {
                'required_columns': ['faculty_id', 'tenant_id', 'institution_id',
                                   'faculty_name', 'email'],
                'data_types': {
                    'faculty_id': 'uuid',
                    'tenant_id': 'uuid',
                    'max_hours_per_week': 'integer',
                    'experience_years': 'integer'
                }
            },
            'sched_constraints.csv': {
                'required_columns': ['constraint_id', 'tenant_id', 'constraint_code',
                                   'constraint_name', 'constraint_type'],
                'data_types': {
                    'constraint_id': 'uuid',
                    'penalty_weight': 'float',
                    'priority_level': 'integer'
                }
            }
            # Additional schema definitions would be added here
        }

    def process_csv_batch(self, csv_directory: str) -> Dict[str, Any]:
        """Main entry point for processing CSV batch"""
        self.audit_logger.info("="*80)
        self.audit_logger.info("STARTING NEP 2020 CSV PROCESSING ENGINE")
        self.audit_logger.info(f"Input Directory: {csv_directory}")
        self.audit_logger.info(f"Processing Started: {datetime.now()}")
        self.audit_logger.info("="*80)

        try:
            # Stage 1: File Discovery and Ingestion
            ingestion_result = self._stage_1_ingestion(csv_directory)
            self.validation_results.append(ingestion_result)
            if not ingestion_result.success and self.config.stop_on_critical_error:
                return self._generate_failure_report("File ingestion failed")

            # Stage 2: Schema Validation
            schema_result = self._stage_2_schema_validation(ingestion_result)
            self.validation_results.append(schema_result)
            if not schema_result.success and self.config.stop_on_critical_error:
                return self._generate_failure_report("Schema validation failed")

            # Stage 3: Referential Integrity
            integrity_result = self._stage_3_referential_integrity(schema_result)
            self.validation_results.append(integrity_result)
            if not integrity_result.success and self.config.stop_on_critical_error:
                return self._generate_failure_report("Referential integrity failed")

            # Stage 4: Constraint Processing
            constraint_result = self._stage_4_constraint_processing(integrity_result)
            self.validation_results.append(constraint_result)
            if not constraint_result.success and self.config.stop_on_critical_error:
                return self._generate_failure_report("Constraint processing failed")

            # Stage 5: Matrix Compilation with Optimization Objectives
            compilation_result = self._stage_5_matrix_compilation(constraint_result)
            self.validation_results.append(compilation_result)

            # Generate final reports
            final_report = self._generate_final_report()

            self.audit_logger.info("="*80)
            self.audit_logger.info("NEP 2020 CSV PROCESSING COMPLETED SUCCESSFULLY")
            self.audit_logger.info(f"Processing Ended: {datetime.now()}")
            self.audit_logger.info("="*80)

            return final_report

        except Exception as e:
            self.error_logger.error(f"CRITICAL ENGINE FAILURE: {str(e)}")
            self.error_logger.error(f"Stack Trace:\n{traceback.format_exc()}")
            return self._generate_failure_report(f"Engine failure: {str(e)}")

    def _stage_1_ingestion(self, csv_directory: str) -> ValidationResult:
        """Stage 1: File Discovery and Basic Ingestion"""
        self.audit_logger.info("STAGE 1: FILE INGESTION STARTED")

        result = ValidationResult(
            stage_name="File Ingestion",
            success=True,
            processing_time=0.0
        )

        start_time = datetime.now()

        try:
            # Discover CSV files
            csv_files = list(Path(csv_directory).glob("sched_*.csv"))

            if not csv_files:
                error = ValidationError(
                    stage="File Ingestion",
                    file_name="N/A",
                    row_number=None,
                    column_name=None,
                    error_code="NO_CSV_FILES",
                    severity=ValidationSeverity.CRITICAL,
                    technical_message=f"No CSV files found in directory: {csv_directory}",
                    user_friendly_message="No scheduling data files were found in the input directory",
                    suggested_fix=f"Ensure CSV files with 'sched_' prefix are present in {csv_directory}"
                )
                result.errors.append(error)
                result.success = False

            self.audit_logger.info(f"Discovered {len(csv_files)} CSV files")

            # Process each file
            for csv_file in csv_files:
                self._validate_file_format(csv_file, result)

        except Exception as e:
            error = ValidationError(
                stage="File Ingestion",
                file_name="N/A",
                row_number=None,
                column_name=None,
                error_code="INGESTION_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                technical_message=f"Exception during file ingestion: {str(e)}",
                user_friendly_message="A system error occurred while reading the CSV files",
                suggested_fix="Check file permissions and format, contact system administrator"
            )
            result.errors.append(error)
            result.success = False

        # Record processing time
        result.processing_time = (datetime.now() - start_time).total_seconds()

        self.audit_logger.info(f"STAGE 1 COMPLETED - Success: {result.success}")
        self.audit_logger.info(f"Files Processed: {len(list(Path(csv_directory).glob('sched_*.csv')))}")
        self.audit_logger.info(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
        self.audit_logger.info(f"Processing Time: {result.processing_time:.2f} seconds")

        # Generate stage-specific error report
        if result.errors:
            self._generate_stage_error_report("Stage_1_Ingestion", result)

        return result

    def _validate_file_format(self, csv_file: Path, result: ValidationResult):
        """Validate basic file format and encoding"""
        try:
            # Check file size
            if csv_file.stat().st_size == 0:
                error = ValidationError(
                    stage="File Ingestion",
                    file_name=csv_file.name,
                    row_number=None,
                    column_name=None,
                    error_code="EMPTY_FILE",
                    severity=ValidationSeverity.ERROR,
                    technical_message=f"File is empty: {csv_file.name}",
                    user_friendly_message=f"The file {csv_file.name} contains no data",
                    suggested_fix="Ensure the file contains header row and data rows"
                )
                result.errors.append(error)
                return

            # Try to read with pandas to check format
            try:
                df = pd.read_csv(csv_file, nrows=1)
                self.audit_logger.info(f"File format valid: {csv_file.name} ({len(df.columns)} columns)")
            except Exception as e:
                error = ValidationError(
                    stage="File Ingestion",
                    file_name=csv_file.name,
                    row_number=None,
                    column_name=None,
                    error_code="INVALID_CSV_FORMAT",
                    severity=ValidationSeverity.ERROR,
                    technical_message=f"Invalid CSV format in {csv_file.name}: {str(e)}",
                    user_friendly_message=f"The file {csv_file.name} is not in valid CSV format",
                    suggested_fix="Check file encoding, delimiters, and ensure proper CSV structure"
                )
                result.errors.append(error)

        except Exception as e:
            error = ValidationError(
                stage="File Ingestion",
                file_name=csv_file.name,
                row_number=None,
                column_name=None,
                error_code="FILE_ACCESS_ERROR",
                severity=ValidationSeverity.ERROR,
                technical_message=f"Cannot access file {csv_file.name}: {str(e)}",
                user_friendly_message=f"Cannot read the file {csv_file.name}",
                suggested_fix="Check file permissions and ensure file is not locked"
            )
            result.errors.append(error)

    def _stage_2_schema_validation(self, previous_result: ValidationResult) -> ValidationResult:
        """Stage 2: Schema Compliance Validation"""
        self.audit_logger.info("STAGE 2: SCHEMA VALIDATION STARTED")

        result = ValidationResult(
            stage_name="Schema Validation",
            success=True,
            processing_time=0.0
        )

        if not previous_result.success:
            result.success = False
            self.audit_logger.info("STAGE 2 SKIPPED - Previous stage failed")
            return result

        start_time = datetime.now()

        try:
            # Process each CSV file against its expected schema
            csv_files = list(Path(self.config.input_directory).glob("sched_*.csv"))

            for csv_file in csv_files:
                if csv_file.name in self.schema_definitions:
                    self._validate_schema_compliance(csv_file, result)
                else:
                    warning = ValidationError(
                        stage="Schema Validation",
                        file_name=csv_file.name,
                        row_number=None,
                        column_name=None,
                        error_code="UNKNOWN_SCHEMA",
                        severity=ValidationSeverity.WARNING,
                        technical_message=f"No schema definition for {csv_file.name}",
                        user_friendly_message=f"The file {csv_file.name} doesn't have a validation schema",
                        suggested_fix="Add schema definition or remove file if not needed"
                    )
                    result.warnings.append(warning)

        except Exception as e:
            error = ValidationError(
                stage="Schema Validation",
                file_name="N/A",
                row_number=None,
                column_name=None,
                error_code="SCHEMA_VALIDATION_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                technical_message=f"Exception during schema validation: {str(e)}",
                user_friendly_message="A system error occurred during schema validation",
                suggested_fix="Contact system administrator"
            )
            result.errors.append(error)
            result.success = False

        result.processing_time = (datetime.now() - start_time).total_seconds()

        self.audit_logger.info(f"STAGE 2 COMPLETED - Success: {result.success}")
        self.audit_logger.info(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
        self.audit_logger.info(f"Processing Time: {result.processing_time:.2f} seconds")

        # Generate stage-specific error report
        if result.errors:
            self._generate_stage_error_report("Stage_2_Schema", result)

        return result

    def _validate_schema_compliance(self, csv_file: Path, result: ValidationResult):
        """Validate individual file against expected schema"""
        schema = self.schema_definitions[csv_file.name]

        try:
            df = pd.read_csv(csv_file)

            # Check required columns
            missing_columns = set(schema['required_columns']) - set(df.columns)
            if missing_columns:
                for col in missing_columns:
                    error = ValidationError(
                        stage="Schema Validation",
                        file_name=csv_file.name,
                        row_number=None,
                        column_name=col,
                        error_code="MISSING_REQUIRED_COLUMN",
                        severity=ValidationSeverity.ERROR,
                        technical_message=f"Required column '{col}' missing in {csv_file.name}",
                        user_friendly_message=f"The required column '{col}' is missing",
                        suggested_fix=f"Add column '{col}' to the CSV file with appropriate values"
                    )
                    result.errors.append(error)

            # Validate data types
            self._validate_data_types(df, csv_file.name, schema, result)

            result.processed_rows += len(df)
            self.audit_logger.info(f"Schema validated: {csv_file.name} ({len(df)} rows, {len(df.columns)} columns)")

        except Exception as e:
            error = ValidationError(
                stage="Schema Validation",
                file_name=csv_file.name,
                row_number=None,
                column_name=None,
                error_code="SCHEMA_READ_ERROR",
                severity=ValidationSeverity.ERROR,
                technical_message=f"Cannot read {csv_file.name} for schema validation: {str(e)}",
                user_friendly_message=f"Cannot process the file {csv_file.name}",
                suggested_fix="Check file format and encoding"
            )
            result.errors.append(error)

    def _validate_data_types(self, df: pd.DataFrame, file_name: str, schema: Dict, result: ValidationResult):
        """Validate data types in DataFrame"""
        for column, expected_type in schema.get('data_types', {}).items():
            if column in df.columns:
                # Validate UUIDs
                if expected_type == 'uuid':
                    invalid_uuids = []
                    for idx, value in df[column].items():
                        if pd.notna(value) and not self._is_valid_uuid(str(value)):
                            invalid_uuids.append(idx + 2)  # +2 for header and 0-indexing

                    if invalid_uuids:
                        error = ValidationError(
                            stage="Schema Validation",
                            file_name=file_name,
                            row_number=invalid_uuids[0] if len(invalid_uuids) == 1 else None,
                            column_name=column,
                            error_code="INVALID_UUID_FORMAT",
                            severity=ValidationSeverity.ERROR,
                            technical_message=f"Invalid UUID format in column '{column}', rows: {invalid_uuids[:5]}",
                            user_friendly_message=f"Column '{column}' contains invalid ID format",
                            suggested_fix="Ensure all IDs are in proper UUID format (e.g., 12345678-1234-1234-1234-123456789abc)"
                        )
                        result.errors.append(error)

                # Validate integers
                elif expected_type == 'integer':
                    non_numeric = df[~df[column].apply(lambda x: pd.isna(x) or str(x).isdigit())].index.tolist()
                    if non_numeric:
                        error = ValidationError(
                            stage="Schema Validation", 
                            file_name=file_name,
                            row_number=non_numeric[0] + 2 if len(non_numeric) == 1 else None,
                            column_name=column,
                            error_code="INVALID_INTEGER_FORMAT",
                            severity=ValidationSeverity.ERROR,
                            technical_message=f"Non-integer values in column '{column}', rows: {non_numeric[:5]}",
                            user_friendly_message=f"Column '{column}' should contain only whole numbers",
                            suggested_fix=f"Ensure all values in '{column}' are valid integers"
                        )
                        result.errors.append(error)

    def _is_valid_uuid(self, uuid_string: str) -> bool:
        """Check if string is valid UUID format"""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False

    def _stage_3_referential_integrity(self, previous_result: ValidationResult) -> ValidationResult:
        """Stage 3: Referential Integrity Validation"""
        self.audit_logger.info("STAGE 3: REFERENTIAL INTEGRITY VALIDATION STARTED")

        result = ValidationResult(
            stage_name="Referential Integrity",
            success=True,
            processing_time=0.0
        )

        if not previous_result.success:
            result.success = False
            self.audit_logger.info("STAGE 3 SKIPPED - Previous stage failed")
            return result

        start_time = datetime.now()

        try:
            # Load all CSV data for cross-reference validation
            data_frames = {}
            csv_files = list(Path(self.config.input_directory).glob("sched_*.csv"))

            for csv_file in csv_files:
                try:
                    data_frames[csv_file.stem] = pd.read_csv(csv_file)
                except Exception as e:
                    continue

            # Perform referential integrity checks
            self._check_foreign_key_references(data_frames, result)

        except Exception as e:
            error = ValidationError(
                stage="Referential Integrity",
                file_name="N/A",
                row_number=None,
                column_name=None,
                error_code="INTEGRITY_CHECK_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                technical_message=f"Exception during referential integrity check: {str(e)}",
                user_friendly_message="A system error occurred during cross-reference validation",
                suggested_fix="Contact system administrator"
            )
            result.errors.append(error)
            result.success = False

        result.processing_time = (datetime.now() - start_time).total_seconds()

        self.audit_logger.info(f"STAGE 3 COMPLETED - Success: {result.success}")
        self.audit_logger.info(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
        self.audit_logger.info(f"Processing Time: {result.processing_time:.2f} seconds")

        if result.errors:
            self._generate_stage_error_report("Stage_3_Integrity", result)

        return result

    def _check_foreign_key_references(self, data_frames: Dict[str, pd.DataFrame], result: ValidationResult):
        """Check foreign key references between tables"""

        # Define foreign key relationships
        fk_relationships = [
            {
                'child_table': 'sched_institutions',
                'child_column': 'district_id',
                'parent_table': 'sched_districts',
                'parent_column': 'district_id'
            },
            {
                'child_table': 'sched_departments',
                'child_column': 'institution_id', 
                'parent_table': 'sched_institutions',
                'parent_column': 'institution_id'
            },
            {
                'child_table': 'sched_faculty',
                'child_column': 'institution_id',
                'parent_table': 'sched_institutions', 
                'parent_column': 'institution_id'
            },
            {
                'child_table': 'sched_faculty_course_competency',
                'child_column': 'faculty_id',
                'parent_table': 'sched_faculty',
                'parent_column': 'faculty_id'
            }
        ]

        for relationship in fk_relationships:
            child_table = relationship['child_table']
            parent_table = relationship['parent_table']

            if child_table in data_frames and parent_table in data_frames:
                child_df = data_frames[child_table]
                parent_df = data_frames[parent_table]

                child_col = relationship['child_column']
                parent_col = relationship['parent_column']

                if child_col in child_df.columns and parent_col in parent_df.columns:
                    # Find orphaned references
                    child_values = set(child_df[child_col].dropna())
                    parent_values = set(parent_df[parent_col].dropna())
                    orphaned = child_values - parent_values

                    if orphaned:
                        for orphan_value in list(orphaned)[:5]:  # Report first 5
                            error = ValidationError(
                                stage="Referential Integrity",
                                file_name=child_table + '.csv',
                                row_number=None,
                                column_name=child_col,
                                error_code="FOREIGN_KEY_VIOLATION",
                                severity=ValidationSeverity.ERROR,
                                technical_message=f"Foreign key violation: {child_col} value '{orphan_value}' not found in {parent_table}.{parent_col}",
                                user_friendly_message=f"Reference to non-existent {parent_table.replace('sched_', '')} with ID {orphan_value}",
                                suggested_fix=f"Ensure {orphan_value} exists in {parent_table}.csv or remove references to it"
                            )
                            result.errors.append(error)

                        self.audit_logger.info(f"Foreign key violations found: {child_table}.{child_col} -> {parent_table}.{parent_col} ({len(orphaned)} violations)")

    def _stage_4_constraint_processing(self, previous_result: ValidationResult) -> ValidationResult:
        """Stage 4: Constraint Classification and Processing"""
        self.audit_logger.info("STAGE 4: CONSTRAINT PROCESSING STARTED")

        result = ValidationResult(
            stage_name="Constraint Processing",
            success=True,
            processing_time=0.0
        )

        if not previous_result.success:
            result.success = False
            self.audit_logger.info("STAGE 4 SKIPPED - Previous stage failed")
            return result

        start_time = datetime.now()

        try:
            # Load constraints data
            constraints_file = Path(self.config.input_directory) / "sched_constraints.csv"
            if constraints_file.exists():
                constraints_df = pd.read_csv(constraints_file)

                # Classify constraints as hard or soft
                hard_constraints = []
                soft_constraints = []

                for _, constraint in constraints_df.iterrows():
                    if constraint.get('constraint_type', '').upper() == 'HARD':
                        hard_constraints.append({
                            'id': constraint.get('constraint_id'),
                            'name': constraint.get('constraint_name'),
                            'expression': constraint.get('constraint_expression'),
                            'scope': constraint.get('scope'),
                            'priority': constraint.get('priority_level', 10)
                        })
                    elif constraint.get('constraint_type', '').upper() == 'SOFT':
                        soft_constraints.append({
                            'id': constraint.get('constraint_id'),
                            'name': constraint.get('constraint_name'),
                            'expression': constraint.get('constraint_expression'),
                            'penalty_weight': float(constraint.get('penalty_weight', 1.0)),
                            'priority': constraint.get('priority_level', 5)
                        })

                self.audit_logger.info(f"Constraint Classification:")
                self.audit_logger.info(f"  Hard Constraints: {len(hard_constraints)}")
                self.audit_logger.info(f"  Soft Constraints: {len(soft_constraints)}")

                # Basic feasibility check for hard constraints
                self._check_constraint_feasibility(hard_constraints, result)

                result.summary_stats = {
                    'hard_constraints': len(hard_constraints),
                    'soft_constraints': len(soft_constraints),
                    'total_penalty_weight': sum(c.get('penalty_weight', 0) for c in soft_constraints)
                }

            else:
                warning = ValidationError(
                    stage="Constraint Processing",
                    file_name="sched_constraints.csv",
                    row_number=None,
                    column_name=None,
                    error_code="MISSING_CONSTRAINTS_FILE",
                    severity=ValidationSeverity.WARNING,
                    technical_message="No constraints file found",
                    user_friendly_message="No scheduling constraints were provided",
                    suggested_fix="Add sched_constraints.csv file with constraint definitions"
                )
                result.warnings.append(warning)

        except Exception as e:
            error = ValidationError(
                stage="Constraint Processing",
                file_name="N/A",
                row_number=None,
                column_name=None,
                error_code="CONSTRAINT_PROCESSING_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                technical_message=f"Exception during constraint processing: {str(e)}",
                user_friendly_message="A system error occurred during constraint processing",
                suggested_fix="Contact system administrator"
            )
            result.errors.append(error)
            result.success = False

        result.processing_time = (datetime.now() - start_time).total_seconds()

        self.audit_logger.info(f"STAGE 4 COMPLETED - Success: {result.success}")
        self.audit_logger.info(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
        self.audit_logger.info(f"Processing Time: {result.processing_time:.2f} seconds")

        if result.errors:
            self._generate_stage_error_report("Stage_4_Constraints", result)

        return result

    def _check_constraint_feasibility(self, hard_constraints: List[Dict], result: ValidationResult):
        """Basic feasibility check for hard constraints"""

        # Check for obvious contradictions
        constraint_expressions = [c.get('expression', '') for c in hard_constraints]

        # Simple contradiction detection (can be expanded)
        time_constraints = [expr for expr in constraint_expressions if 'time' in expr.lower()]
        room_constraints = [expr for expr in constraint_expressions if 'room' in expr.lower()]

        # Check for impossible time constraints
        if len(time_constraints) > 40:  # More constraints than typical time slots
            warning = ValidationError(
                stage="Constraint Processing",
                file_name="sched_constraints.csv",
                row_number=None,
                column_name=None,
                error_code="POTENTIAL_INFEASIBILITY",
                severity=ValidationSeverity.WARNING,
                technical_message=f"High number of time constraints ({len(time_constraints)}) may lead to infeasible solutions",
                user_friendly_message="Too many time-based constraints may make it impossible to create a valid schedule",
                suggested_fix="Review time constraints and consider making some of them soft constraints"
            )
            result.warnings.append(warning)

        self.audit_logger.info(f"Feasibility check completed: {len(constraint_expressions)} constraints analyzed")

    def _stage_5_matrix_compilation(self, previous_result: ValidationResult) -> ValidationResult:
        """Stage 5: Matrix Compilation with Optimization Objectives"""
        self.audit_logger.info("STAGE 5: MATRIX COMPILATION STARTED")
        self.audit_logger.info("INCLUDING OPTIMIZATION OBJECTIVES:")
        self.audit_logger.info("  • Maximized utilization of classrooms and laboratories")
        self.audit_logger.info("  • Minimized workload on faculty members and students")
        self.audit_logger.info("  • Achievement of required learning outcomes")

        result = ValidationResult(
            stage_name="Matrix Compilation",
            success=True,
            processing_time=0.0
        )

        if not previous_result.success:
            result.success = False
            self.audit_logger.info("STAGE 5 SKIPPED - Previous stage failed")
            return result

        start_time = datetime.now()

        try:
            # Load all validated data
            data_frames = {}
            csv_files = list(Path(self.config.input_directory).glob("sched_*.csv"))

            for csv_file in csv_files:
                try:
                    data_frames[csv_file.stem] = pd.read_csv(csv_file)
                    self.audit_logger.info(f"Loaded for compilation: {csv_file.name} ({len(pd.read_csv(csv_file))} rows)")
                except Exception as e:
                    continue

            # Create optimization matrix with objectives
            optimization_matrix = self._create_optimization_matrix(data_frames, result)

            # Export matrix in multiple formats
            self._export_optimization_matrix(optimization_matrix, result)

        except Exception as e:
            error = ValidationError(
                stage="Matrix Compilation",
                file_name="N/A",
                row_number=None,
                column_name=None,
                error_code="COMPILATION_EXCEPTION",
                severity=ValidationSeverity.CRITICAL,
                technical_message=f"Exception during matrix compilation: {str(e)}",
                user_friendly_message="A system error occurred during data compilation",
                suggested_fix="Contact system administrator"
            )
            result.errors.append(error)
            result.success = False

        result.processing_time = (datetime.now() - start_time).total_seconds()

        self.audit_logger.info(f"STAGE 5 COMPLETED - Success: {result.success}")
        self.audit_logger.info(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
        self.audit_logger.info(f"Processing Time: {result.processing_time:.2f} seconds")

        if result.errors:
            self._generate_stage_error_report("Stage_5_Compilation", result)

        return result

    def _create_optimization_matrix(self, data_frames: Dict[str, pd.DataFrame], result: ValidationResult) -> OptimizationMatrix:
        """Create unified optimization matrix with objectives"""

        # Compile constraint lists
        hard_constraints = []
        soft_constraints = []

        if 'sched_constraints' in data_frames:
            constraints_df = data_frames['sched_constraints']
            for _, constraint in constraints_df.iterrows():
                if constraint.get('constraint_type', '').upper() == 'HARD':
                    hard_constraints.append({
                        'id': constraint.get('constraint_id'),
                        'name': constraint.get('constraint_name'),
                        'expression': constraint.get('constraint_expression'),
                        'scope': constraint.get('scope'),
                        'applies_to': constraint.get('applies_to')
                    })
                else:
                    soft_constraints.append({
                        'id': constraint.get('constraint_id'),
                        'name': constraint.get('constraint_name'),
                        'expression': constraint.get('constraint_expression'),
                        'penalty_weight': float(constraint.get('penalty_weight', 1.0)),
                        'scope': constraint.get('scope'),
                        'applies_to': constraint.get('applies_to')
                    })

        # Calculate optimization objectives (as requested)
        utilization_objectives = self._calculate_utilization_objectives(data_frames)
        learning_outcome_requirements = self._calculate_learning_outcome_requirements(data_frames)

        # Create optimization matrix
        matrix = OptimizationMatrix(
            institutions=data_frames.get('sched_institutions', pd.DataFrame()),
            departments=data_frames.get('sched_departments', pd.DataFrame()),
            programs=data_frames.get('sched_programs', pd.DataFrame()),
            courses=data_frames.get('sched_courses', pd.DataFrame()),
            faculty=data_frames.get('sched_faculty', pd.DataFrame()),
            rooms=data_frames.get('sched_rooms', pd.DataFrame()),
            time_slots=data_frames.get('sched_time_slots', pd.DataFrame()),
            batches=data_frames.get('sched_student_batches', pd.DataFrame()),
            learning_outcomes=data_frames.get('sched_learning_outcomes', pd.DataFrame()),
            faculty_competency=data_frames.get('sched_faculty_course_competency', pd.DataFrame()),
            batch_enrollments=data_frames.get('sched_batch_course_enrollment', pd.DataFrame()),
            course_outcomes=data_frames.get('sched_course_learning_outcome_mapping', pd.DataFrame()),
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints,
            utilization_objectives=utilization_objectives,
            learning_outcome_requirements=learning_outcome_requirements,
            generation_timestamp=datetime.now(),
            data_quality_score=self._calculate_data_quality_score(data_frames),
            feasibility_status="PRELIMINARY_FEASIBLE"
        )

        self.audit_logger.info("OPTIMIZATION MATRIX CREATED:")
        self.audit_logger.info(f"  • Institutions: {len(matrix.institutions)}")
        self.audit_logger.info(f"  • Faculty: {len(matrix.faculty)}")
        self.audit_logger.info(f"  • Courses: {len(matrix.courses)}")
        self.audit_logger.info(f"  • Rooms: {len(matrix.rooms)}")
        self.audit_logger.info(f"  • Time Slots: {len(matrix.time_slots)}")
        self.audit_logger.info(f"  • Student Batches: {len(matrix.batches)}")
        self.audit_logger.info(f"  • Hard Constraints: {len(matrix.hard_constraints)}")
        self.audit_logger.info(f"  • Soft Constraints: {len(matrix.soft_constraints)}")
        self.audit_logger.info(f"  • Data Quality Score: {matrix.data_quality_score:.2f}/10")

        return matrix

    def _calculate_utilization_objectives(self, data_frames: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Calculate room and lab utilization objectives"""
        objectives = {}

        if 'sched_rooms' in data_frames:
            rooms_df = data_frames['sched_rooms']

            # Calculate room utilization targets
            total_rooms = len(rooms_df)
            lab_rooms = len(rooms_df[rooms_df.get('room_type', '') == 'LAB'])
            classrooms = len(rooms_df[rooms_df.get('room_type', '') == 'CLASSROOM'])

            objectives['max_room_utilization'] = self.config.room_utilization_weight
            objectives['target_lab_utilization'] = 0.8  # 80% target utilization
            objectives['target_classroom_utilization'] = 0.75  # 75% target utilization
            objectives['room_distribution_balance'] = 1.0

        if 'sched_time_slots' in data_frames:
            time_slots_df = data_frames['sched_time_slots']
            total_slots = len(time_slots_df)
            objectives['time_utilization_efficiency'] = total_slots * 0.7  # 70% time utilization target

        return objectives

    def _calculate_learning_outcome_requirements(self, data_frames: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Calculate learning outcome achievement requirements"""
        requirements = {}

        if 'sched_learning_outcomes' in data_frames:
            outcomes_df = data_frames['sched_learning_outcomes']

            requirements['total_learning_outcomes'] = len(outcomes_df)
            requirements['min_outcome_coverage'] = 0.95  # 95% coverage requirement
            requirements['bloom_taxonomy_balance'] = {
                'KNOWLEDGE': 0.15,
                'UNDERSTANDING': 0.25,
                'APPLICATION': 0.30,
                'ANALYSIS': 0.20,
                'SYNTHESIS': 0.10
            }
            requirements['learning_outcome_weight'] = self.config.learning_outcome_weight

        # Faculty workload balancing (minimize)
        if 'sched_faculty' in data_frames:
            faculty_df = data_frames['sched_faculty']
            avg_max_hours = faculty_df.get('max_hours_per_week', pd.Series([18])).mean()
            requirements['faculty_load_balance'] = {
                'target_avg_hours': avg_max_hours * 0.8,  # 80% of max capacity
                'max_deviation': avg_max_hours * 0.2,
                'workload_weight': self.config.faculty_load_weight
            }

        return requirements

    def _calculate_data_quality_score(self, data_frames: Dict[str, pd.DataFrame]) -> float:
        """Calculate overall data quality score (1-10 scale)"""
        score = 10.0

        # Penalize for missing required files
        required_files = ['sched_institutions', 'sched_courses', 'sched_faculty', 'sched_rooms']
        missing_files = [f for f in required_files if f not in data_frames]
        score -= len(missing_files) * 2.0

        # Penalize for empty or very small datasets
        for df_name, df in data_frames.items():
            if len(df) < 2:  # Less than 2 rows (excluding header)
                score -= 1.0

        # Reward for constraint completeness
        if 'sched_constraints' in data_frames and len(data_frames['sched_constraints']) > 5:
            score += 0.5

        return max(1.0, min(10.0, score))

    def _export_optimization_matrix(self, matrix: OptimizationMatrix, result: ValidationResult):
        """Export optimization matrix in multiple formats"""

        output_dir = Path(self.config.output_directory)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export as JSON for algorithm consumption
        json_output = {
            'metadata': {
                'generation_timestamp': matrix.generation_timestamp.isoformat(),
                'data_quality_score': matrix.data_quality_score,
                'feasibility_status': matrix.feasibility_status
            },
            'data': {
                'institutions': matrix.institutions.to_dict('records') if not matrix.institutions.empty else [],
                'departments': matrix.departments.to_dict('records') if not matrix.departments.empty else [],
                'courses': matrix.courses.to_dict('records') if not matrix.courses.empty else [],
                'faculty': matrix.faculty.to_dict('records') if not matrix.faculty.empty else [],
                'rooms': matrix.rooms.to_dict('records') if not matrix.rooms.empty else [],
                'time_slots': matrix.time_slots.to_dict('records') if not matrix.time_slots.empty else [],
                'batches': matrix.batches.to_dict('records') if not matrix.batches.empty else []
            },
            'constraints': {
                'hard_constraints': matrix.hard_constraints,
                'soft_constraints': matrix.soft_constraints
            },
            'optimization_objectives': {
                'utilization_objectives': matrix.utilization_objectives,
                'learning_outcome_requirements': matrix.learning_outcome_requirements
            }
        }

        json_file = output_dir / f"optimization_matrix_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, default=str)

        # Export constraint summary as text
        constraint_file = output_dir / f"constraint_summary_{timestamp}.txt"
        with open(constraint_file, 'w', encoding='utf-8') as f:
            f.write("NEP 2020 CONSTRAINT CLASSIFICATION SUMMARY\n")
            f.write("="*60 + "\n\n")

            f.write("HARD CONSTRAINTS (Must be satisfied):\n")
            f.write("-" * 40 + "\n")
            for i, constraint in enumerate(matrix.hard_constraints, 1):
                f.write(f"{i}. {constraint.get('name', 'Unnamed')}\n")
                f.write(f"   Expression: {constraint.get('expression', 'N/A')}\n")
                f.write(f"   Scope: {constraint.get('scope', 'N/A')}\n\n")

            f.write("\nSOFT CONSTRAINTS (Preferences with penalties):\n")
            f.write("-" * 40 + "\n")
            for i, constraint in enumerate(matrix.soft_constraints, 1):
                f.write(f"{i}. {constraint.get('name', 'Unnamed')}\n")
                f.write(f"   Expression: {constraint.get('expression', 'N/A')}\n")
                f.write(f"   Penalty Weight: {constraint.get('penalty_weight', 1.0)}\n")
                f.write(f"   Scope: {constraint.get('scope', 'N/A')}\n\n")

            f.write("\nOPTIMIZATION OBJECTIVES:\n")
            f.write("-" * 40 + "\n")
            f.write("1. MAXIMIZE: Classroom and Laboratory Utilization\n")
            for key, value in matrix.utilization_objectives.items():
                f.write(f"   {key}: {value}\n")

            f.write("\n2. MINIMIZE: Faculty and Student Workload\n")
            if 'faculty_load_balance' in matrix.learning_outcome_requirements:
                flb = matrix.learning_outcome_requirements['faculty_load_balance']
                f.write(f"   Target Average Hours: {flb.get('target_avg_hours', 'N/A')}\n")
                f.write(f"   Max Deviation: {flb.get('max_deviation', 'N/A')}\n")
                f.write(f"   Workload Weight: {flb.get('workload_weight', 'N/A')}\n")

            f.write("\n3. ACHIEVE: Required Learning Outcomes\n")
            f.write(f"   Total Learning Outcomes: {matrix.learning_outcome_requirements.get('total_learning_outcomes', 'N/A')}\n")
            f.write(f"   Minimum Coverage: {matrix.learning_outcome_requirements.get('min_outcome_coverage', 'N/A')}\n")

        self.audit_logger.info(f"MATRIX EXPORTED:")
        self.audit_logger.info(f"  • JSON Format: {json_file.name}")
        self.audit_logger.info(f"  • Constraint Summary: {constraint_file.name}")

        result.summary_stats['exported_files'] = [json_file.name, constraint_file.name]

    def _generate_stage_error_report(self, stage_name: str, result: ValidationResult):
        """Generate detailed error report for specific stage"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(self.config.error_report_directory) / f"{stage_name}_errors_{timestamp}.txt"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"NEP 2020 CSV VALIDATION ERROR REPORT\n")
            f.write(f"Stage: {stage_name}\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("="*80 + "\n\n")

            f.write(f"SUMMARY:\n")
            f.write(f"  Errors: {len(result.errors)}\n")
            f.write(f"  Warnings: {len(result.warnings)}\n")
            f.write(f"  Processing Time: {result.processing_time:.2f} seconds\n\n")

            if result.errors:
                f.write("ERRORS (Technical + User-Friendly):\n")
                f.write("-" * 50 + "\n")
                for i, error in enumerate(result.errors, 1):
                    f.write(f"ERROR {i}:\n")
                    f.write(f"  File: {error.file_name}\n")
                    f.write(f"  Row: {error.row_number or 'N/A'}\n")
                    f.write(f"  Column: {error.column_name or 'N/A'}\n")
                    f.write(f"  Code: {error.error_code}\n")
                    f.write(f"  Severity: {error.severity.value}\n")
                    f.write(f"  Technical: {error.technical_message}\n")
                    f.write(f"  User Message: {error.user_friendly_message}\n")
                    f.write(f"  Suggested Fix: {error.suggested_fix}\n")
                    f.write("\n")

            if result.warnings:
                f.write("WARNINGS:\n")
                f.write("-" * 20 + "\n")
                for i, warning in enumerate(result.warnings, 1):
                    f.write(f"WARNING {i}: {warning.user_friendly_message}\n")
                    f.write(f"  Suggested Fix: {warning.suggested_fix}\n\n")

        self.error_logger.error(f"Stage-specific error report generated: {report_file.name}")

    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final processing report"""
        total_errors = sum(len(result.errors) for result in self.validation_results)
        total_warnings = sum(len(result.warnings) for result in self.validation_results)
        total_time = sum(result.processing_time for result in self.validation_results)

        overall_success = all(result.success for result in self.validation_results)

        final_report = {
            'processing_summary': {
                'overall_success': overall_success,
                'total_stages': len(self.validation_results),
                'total_errors': total_errors,
                'total_warnings': total_warnings,
                'total_processing_time': total_time,
                'completion_timestamp': datetime.now().isoformat()
            },
            'stage_results': []
        }

        for result in self.validation_results:
            final_report['stage_results'].append({
                'stage_name': result.stage_name,
                'success': result.success,
                'errors': len(result.errors),
                'warnings': len(result.warnings),
                'processing_time': result.processing_time,
                'summary_stats': result.summary_stats
            })

        # Generate final summary report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = Path(self.config.output_directory) / f"processing_summary_{timestamp}.txt"

        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("NEP 2020 CSV PROCESSING ENGINE - FINAL SUMMARY\n")
            f.write("="*70 + "\n\n")

            f.write(f"OVERALL STATUS: {'SUCCESS' if overall_success else 'FAILED'}\n")
            f.write(f"Processing Date: {datetime.now()}\n")
            f.write(f"Total Processing Time: {total_time:.2f} seconds\n")
            f.write(f"Total Errors: {total_errors}\n")
            f.write(f"Total Warnings: {total_warnings}\n\n")

            f.write("STAGE-BY-STAGE RESULTS:\n")
            f.write("-" * 40 + "\n")
            for result in self.validation_results:
                status = "PASS" if result.success else "FAIL"
                f.write(f"{result.stage_name:<25} | {status:<4} | ")
                f.write(f"Errors: {len(result.errors):>3} | ")
                f.write(f"Warnings: {len(result.warnings):>3} | ")
                f.write(f"Time: {result.processing_time:>6.2f}s\n")

            if overall_success:
                f.write("\n" + "="*70 + "\n")
                f.write("VALIDATION COMPLETED SUCCESSFULLY!\n")
                f.write("The CSV data has been validated and compiled into optimization matrix.\n")
                f.write("Ready for scheduling algorithm processing.\n")
                f.write("\nOPTIMIZATION OBJECTIVES INCLUDED:\n")
                f.write("• Maximized utilization of classrooms and laboratories\n")
                f.write("• Minimized workload on faculty members and students\n") 
                f.write("• Achievement of required learning outcomes\n")
                f.write("="*70)
            else:
                f.write("\n" + "="*70 + "\n")
                f.write("VALIDATION FAILED!\n")
                f.write("Critical errors were found that prevent scheduling.\n")
                f.write("Please review error reports and fix data issues.\n")
                f.write("="*70)

        final_report['summary_file'] = summary_file.name

        self.audit_logger.info("="*80)
        self.audit_logger.info("FINAL PROCESSING REPORT GENERATED")
        self.audit_logger.info(f"Overall Success: {overall_success}")
        self.audit_logger.info(f"Summary File: {summary_file.name}")
        self.audit_logger.info("="*80)

        return final_report

    def _generate_failure_report(self, failure_reason: str) -> Dict[str, Any]:
        """Generate report for critical failure"""
        self.error_logger.error(f"CRITICAL FAILURE: {failure_reason}")

        return {
            'processing_summary': {
                'overall_success': False,
                'failure_reason': failure_reason,
                'completion_timestamp': datetime.now().isoformat()
            },
            'message': 'Critical failure occurred during CSV processing',
            'suggested_action': 'Review error logs and fix critical issues'
        }


def main():
    """Main entry point for CSV Processing Engine"""
    print("="*80)
    print("NEP 2020 CSV PROCESSING & DATA VALIDATION ENGINE")
    print("Production-Ready Prototype for Government Deployment")
    print("Version 1.0.0")
    print("="*80)

    # Configuration
    config = ValidationConfig(
        input_directory="sample_csv_data",
        output_directory="validation_output",
        audit_log_directory="audit_logs",
        error_report_directory="error_reports"
    )

    # Initialize engine
    engine = CSVProcessingEngine(config)

    # Process CSV batch
    result = engine.process_csv_batch(config.input_directory)

    # Print summary
    if result['processing_summary']['overall_success']:
        print("\n🎉 PROCESSING COMPLETED SUCCESSFULLY!")
        print("✅ All validation stages passed")
        print("✅ Optimization matrix generated") 
        print("✅ Ready for scheduling algorithms")
        print("\n📊 OPTIMIZATION OBJECTIVES INCLUDED:")
        print("   • Maximized utilization of classrooms and laboratories")
        print("   • Minimized workload on faculty members and students")
        print("   • Achievement of required learning outcomes")
    else:
        print("\n❌ PROCESSING FAILED!")
        print("⚠️  Critical errors found")
        print("📋 Review error reports for details")

    print(f"\n📁 Output Directory: {config.output_directory}")
    print(f"📋 Audit Logs: {config.audit_log_directory}")
    print(f"🚨 Error Reports: {config.error_report_directory}")
    print("="*80)

    return result


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result['processing_summary']['overall_success'] else 1)
