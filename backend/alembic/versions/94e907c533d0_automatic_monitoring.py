"""automatic camera monitoring and weather context

Revision ID: 94e907c533d0
Revises: 365240ccd2b6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "94e907c533d0"
down_revision: Union[str, Sequence[str], None] = "365240ccd2b6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    capturemode=sa.Enum("MANUAL","AUTOMATIC",name="capturemode")
    capturemode.create(op.get_bind(),checkfirst=True)
    op.create_table(
        "monitoring_sources",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("equipment_id",sa.String(36),sa.ForeignKey("equipment.id"),nullable=False),
        sa.Column("station_name",sa.String(180),nullable=False),
        sa.Column("latitude",sa.Float(),nullable=False),
        sa.Column("longitude",sa.Float(),nullable=False),
        sa.Column("rgb_camera_url",sa.String(1000),nullable=False),
        sa.Column("thermal_camera_url",sa.String(1000),nullable=False),
        sa.Column("capture_interval_minutes",sa.Integer(),nullable=False,server_default="10"),
        sa.Column("monitoring_enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("last_capture_at",sa.DateTime(),nullable=True),
        sa.Column("next_capture_at",sa.DateTime(),nullable=True),
        sa.Column("last_error",sa.Text(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),
    )
    op.create_index("ix_monitoring_sources_user_id","monitoring_sources",["user_id"])
    op.create_index("ix_monitoring_sources_equipment_id","monitoring_sources",["equipment_id"],unique=True)
    op.create_index("ix_monitoring_sources_next_capture_at","monitoring_sources",["next_capture_at"])
    with op.batch_alter_table("inspections") as batch:
        batch.add_column(sa.Column("monitoring_source_id",sa.String(36),nullable=True))
        batch.add_column(sa.Column("capture_mode",capturemode,nullable=False,server_default="MANUAL"))
        batch.create_foreign_key("fk_inspections_monitoring_source","monitoring_sources",["monitoring_source_id"],["id"])
        batch.create_index("ix_inspections_monitoring_source_id",["monitoring_source_id"])
    op.add_column("inspection_environments",sa.Column("station_name",sa.String(180),nullable=True))
    op.add_column("inspection_environments",sa.Column("latitude",sa.Float(),nullable=True))
    op.add_column("inspection_environments",sa.Column("longitude",sa.Float(),nullable=True))
    op.add_column("inspection_environments",sa.Column("weather_source",sa.String(80),nullable=True))
    op.add_column("inspection_environments",sa.Column("weather_observed_at",sa.DateTime(),nullable=True))

def downgrade() -> None:
    for column in ("weather_observed_at","weather_source","longitude","latitude","station_name"):
        op.drop_column("inspection_environments",column)
    with op.batch_alter_table("inspections") as batch:
        batch.drop_index("ix_inspections_monitoring_source_id")
        batch.drop_constraint("fk_inspections_monitoring_source",type_="foreignkey")
        batch.drop_column("capture_mode")
        batch.drop_column("monitoring_source_id")
    op.drop_index("ix_monitoring_sources_next_capture_at",table_name="monitoring_sources")
    op.drop_index("ix_monitoring_sources_equipment_id",table_name="monitoring_sources")
    op.drop_index("ix_monitoring_sources_user_id",table_name="monitoring_sources")
    op.drop_table("monitoring_sources")
    sa.Enum(name="capturemode").drop(op.get_bind(),checkfirst=True)
